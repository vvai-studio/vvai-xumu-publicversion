"""Behavioral tests of the local key page: key checks, shell start files, and the page server end to end (local
loopback only; the online check and the save are fakes, so nothing touches the registry, a real shell file or the
network)."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import urlsplit, quote

import key_setup as ks

KEY = 'sk-test1234567890abcdef'


class KeyShapeTests(unittest.TestCase):
    def test_real_looking_keys_pass(self):
        self.assertTrue(ks.valid_key(KEY))
        self.assertTrue(ks.valid_key('a1b2c3d4-e5f6_7890.XYZ'))

    def test_placeholders_spaces_and_shell_breakers_fail(self):
        for bad in ('sk-你的新密钥', 'sk-abc def123', 'short', '', "sk-abc'1234567", 'sk-$HOME12345', 'x' * 513):
            self.assertFalse(ks.valid_key(bad), bad)


class ShellFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-keys-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def test_start_file_follows_the_shell(self):
        self.assertEqual(ks.rc_file(self.home, '/bin/zsh', 'darwin').name, '.zshrc')
        self.assertEqual(ks.rc_file(self.home, '', 'darwin').name, '.zshrc')
        self.assertEqual(ks.rc_file(self.home, '/bin/bash', 'darwin').name, '.bash_profile')
        self.assertEqual(ks.rc_file(self.home, '/bin/bash', 'linux').name, '.bashrc')
        self.assertEqual(ks.rc_file(self.home, '/bin/fish', 'linux').name, '.profile')

    def test_saving_twice_replaces_the_line_and_keeps_the_rest(self):
        rc = self.home / '.zshrc'
        rc.write_text('alias ll="ls -l"\nexport VVAI_API_KEY="sk-old-0000000"\nexport PATH=$PATH:/x\n', encoding='utf-8')
        where = ks.save('VVAI_API_KEY', KEY, platform='darwin', home=self.home, shell='/bin/zsh')
        ks.save('VVAI_API_KEY', KEY + 'z', platform='darwin', home=self.home, shell='/bin/zsh')
        self.assertEqual(where, str(rc))
        text = rc.read_text(encoding='utf-8')
        self.assertEqual(text.count('VVAI_API_KEY'), 1)
        self.assertIn('alias ll="ls -l"', text)
        self.assertIn('export PATH=$PATH:/x', text)
        self.assertNotIn('sk-old', text)
        self.assertEqual(ks.read_rc(rc, 'VVAI_API_KEY'), KEY + 'z')

    def test_load_user_env_takes_the_saved_value_over_a_stale_one(self):
        ks.save('VVAI_API_KEY', KEY, platform='linux', home=self.home, shell='/bin/bash')
        env = {'VVAI_API_KEY': 'sk-stale-111111'}
        loaded = ks.load_user_env(('VVAI_API_KEY', 'DASHSCOPE_API_KEY'), env, platform='linux', home=self.home,
                                  shell='/bin/bash')
        self.assertEqual((loaded, env['VVAI_API_KEY']), (['VVAI_API_KEY'], KEY))
        self.assertNotIn('DASHSCOPE_API_KEY', env)
        self.assertEqual(ks.load_user_env(('VVAI_API_KEY',), env, platform='linux', home=self.home, shell='/bin/bash'), [])

    def test_a_key_saved_under_another_shell_is_still_found(self):
        ks.save('VVAI_API_KEY', KEY, platform='linux', home=self.home, shell='/bin/bash')
        kw = {'platform': 'linux', 'home': self.home, 'shell': ''}
        self.assertEqual(ks.key_state('VVAI_API_KEY', {}, **kw), 'saved')
        env = {}
        self.assertEqual(ks.load_user_env(('VVAI_API_KEY',), env, **kw), ['VVAI_API_KEY'])
        self.assertEqual(env['VVAI_API_KEY'], KEY)

    def test_another_shell_file_does_not_replace_an_inherited_key(self):
        ks.save('VVAI_API_KEY', KEY, platform='linux', home=self.home, shell='/bin/bash')
        env = {'VVAI_API_KEY': 'sk-inherited-111111'}
        self.assertEqual(ks.load_user_env(('VVAI_API_KEY',), env, platform='linux', home=self.home, shell=''), [])
        self.assertEqual(env['VVAI_API_KEY'], 'sk-inherited-111111')

    def test_no_key_anywhere_is_not_configured(self):
        self.assertIsNone(ks.key_state('VVAI_API_KEY', {}, platform='linux', home=self.home, shell='/bin/bash'))

    def test_a_key_only_this_process_holds_is_not_called_saved(self):
        state = ks.key_state('VVAI_API_KEY', {'VVAI_API_KEY': KEY}, platform='linux', home=self.home, shell='/bin/bash')
        self.assertEqual(state, 'session')

    def test_unwritable_start_file_folder_cannot_save(self):
        with mock.patch.object(ks.os, 'access', lambda path, mode: False):
            self.assertFalse(ks.can_save(platform='linux', home=self.home, shell='/bin/bash'))
        self.assertTrue(ks.can_save(platform='linux', home=self.home, shell='/bin/bash'))


class SandboxTests(unittest.TestCase):
    """A sandbox can read the saved key but refuse to store one; Windows reports that when the key is opened for write."""
    def fake_winreg(self, refuse):
        def open_key(*a):
            if refuse:
                raise PermissionError(5, 'denied')
            return mock.Mock()
        return mock.Mock(HKEY_CURRENT_USER=0, KEY_SET_VALUE=2, OpenKey=open_key)

    def test_windows_refusal_is_detected_before_the_page_opens(self):
        with mock.patch.object(ks, '_winreg', lambda: self.fake_winreg(True)):
            self.assertFalse(ks.can_save(platform='win32'))
        with mock.patch.object(ks, '_winreg', lambda: self.fake_winreg(False)):
            self.assertTrue(ks.can_save(platform='win32'))

    def test_help_gives_a_command_to_run_outside_and_no_host_name(self):
        text = ks.no_save_help('VVAI_API_KEY', platform='win32')
        self.assertIn('--var VVAI_API_KEY --replace', text)
        self.assertIn('key_setup.py', text)
        self.assertNotIn('Claude', text)
        self.assertNotIn('Codex', text)


class AskOnceTests(unittest.TestCase):
    def main(self, state, *argv, writable=True):
        pages, out = [], []
        with mock.patch.object(ks, 'key_state', lambda var: state), \
                mock.patch.object(ks, 'can_save', lambda: writable), \
                mock.patch.object(ks, 'run', lambda *a: pages.append(a) or 0), \
                mock.patch('builtins.print', lambda *a: out.append(' '.join(map(str, a)))):
            code = ks.main(list(argv))
        return code, bool(pages), '\n'.join(out)

    def test_status_reports_and_never_opens_the_page(self):
        self.assertEqual(self.main('saved', '--status')[:2], (0, False))
        self.assertEqual(self.main('session', '--status')[:2], (0, False))
        self.assertEqual(self.main(None, '--status')[:2], (1, False))

    def test_a_usable_key_is_not_asked_for_again(self):
        for state in ('saved', 'session'):
            code, opened, text = self.main(state)
            self.assertEqual((code, opened), (0, False))
            self.assertIn('--replace', text)

    def test_the_page_opens_on_first_setup_and_on_a_key_change(self):
        self.assertTrue(self.main(None)[1])
        self.assertTrue(self.main('saved', '--replace')[1])

    def test_a_sandbox_gets_the_way_out_instead_of_a_page_that_cannot_save(self):
        for args in ((None,), ('saved', '--replace')):
            code, opened, text = self.main(*args, writable=False)
            self.assertEqual((code, opened), (4, False))
            self.assertIn('--replace', text)


class PageServerTests(unittest.TestCase):
    def start(self, verify=None, saver=None):
        self.saved = []
        saver = saver or (lambda var, key: self.saved.append((var, key)) or 'test-store')
        srv = ks.make_server('VVAI_API_KEY', verify, saver)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(lambda: (srv.shutdown(), t.join(5)) if t.is_alive() else None)
        u = urlsplit(srv.url)
        self.srv, self.host, self.port, self.path = srv, u.hostname, u.port, u.path
        return t

    def request(self, method, path=None, body=None, headers=None):
        c = http.client.HTTPConnection(self.host, self.port, timeout=5)
        h = {'Content-Type': 'application/x-www-form-urlencoded'} if body is not None else {}
        h.update(headers or {})
        c.request(method, path or self.path, body=body, headers=h)
        r = c.getresponse()
        data = r.read().decode('utf-8')
        c.close()
        return r.status, data

    def post_key(self, key, headers=None):
        status, data = self.request('POST', body='key=' + quote(key), headers=headers)
        return status, (json.loads(data) if status == 200 else data)

    def test_page_needs_the_one_time_path(self):
        self.start()
        self.assertEqual(self.request('GET', '/')[0], 404)
        status, page = self.request('GET')
        self.assertEqual(status, 200)
        self.assertIn('VVAI_API_KEY', page)
        self.assertIn('管理密钥', page)

    def test_other_origins_and_hosts_are_refused(self):
        self.start()
        self.assertEqual(self.post_key(KEY, {'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.post_key(KEY, {'Host': f'attacker.example:{self.port}'})[0], 403)
        self.assertEqual(self.saved, [])

    def test_bad_key_and_failed_check_save_nothing(self):
        self.start(verify=lambda key: (False, '密钥不对或已作废（401）'))
        self.assertFalse(self.post_key('sk-你的新密钥')[1]['ok'])
        reply = self.post_key(KEY)[1]
        self.assertFalse(reply['ok'])
        self.assertIn('401', reply['msg'])
        self.assertEqual(self.saved, [])

    def test_good_key_is_checked_saved_once_and_the_server_stops(self):
        checked = []
        t = self.start(verify=lambda key: (checked.append(key) or True, '余额 31.5 ⚡'))
        reply = self.post_key(KEY, {'Origin': f'http://127.0.0.1:{self.port}'})[1]
        self.assertTrue(reply['ok'])
        self.assertIn('余额 31.5', reply['msg'])
        self.assertNotIn(KEY, reply['msg'])
        self.assertEqual((checked, self.saved), ([KEY], [('VVAI_API_KEY', KEY)]))
        self.assertEqual(self.srv.result, {'var': 'VVAI_API_KEY', 'where': 'test-store', 'note': '余额 31.5 ⚡'})
        t.join(5)
        self.assertFalse(t.is_alive())

    def test_a_refused_save_tells_the_user_what_to_do(self):
        def refuse(var, key):
            raise PermissionError(5, 'denied')
        self.start(saver=refuse)
        reply = self.post_key(KEY)[1]
        self.assertFalse(reply['ok'])
        self.assertIn('沙箱', reply['msg'])
        self.assertNotIn(KEY, reply['msg'])


if __name__ == '__main__':
    unittest.main()
