from __future__ import absolute_import
import sys
import atexit
import ssl
import threading
import binascii
from functools import wraps
import _sslkeylog


if sys.version_info[0] >= 3:
    string_types = str,
else:
    string_types = basestring,  # noqa: F821


def get_client_random(sock):
    sock = getattr(sock, '_sslobj', sock)
    return _sslkeylog.get_client_random(sock)


def get_master_key(sock):
    sock = getattr(sock, '_sslobj', sock)
    return _sslkeylog.get_master_key(sock)


def get_keylog_line(sock):
    return "CLIENT_RANDOM {} {}".format(
        binascii.hexlify(get_client_random(sock)).decode("utf-8"),
        binascii.hexlify(get_master_key(sock)).decode("utf-8"))


_lock = threading.Lock()
_keylog_callback = None
_log_file = None


@atexit.register
def _cleanup():
    if _log_file is not None:
        _log_file.close()


def set_keylog(dest):
    global _keylog_callback, _log_file

    patch()

    if callable(dest):
        _keylog_callback = dest
    else:
        if isinstance(dest, string_types):
            log_file = open(dest, 'a')
        else:
            log_file = dest

        def _keylog(sock, line):
            with _lock:
                log_file.write(line + '\n')
                log_file.flush()

        _keylog_callback = _keylog

    if _log_file is not None:
        _log_file.close()
        _log_file = None

    if isinstance(dest, string_types):
        _log_file = log_file


_patched = False
_original_do_handshake = None


@wraps(ssl.SSLSocket.do_handshake)
def _do_handshake(self, *args, **kwargs):
    _original_do_handshake(self, *args, **kwargs)

    if _keylog_callback is not None:
        _keylog_callback(self, get_keylog_line(self))


def patch():
    global _patched, _original_do_handshake

    if _patched:
        return

    _original_do_handshake = ssl.SSLSocket.do_handshake
    ssl.SSLSocket.do_handshake = _do_handshake

    _patched = True


def unpatch():
    global _patched, _original_do_handshake

    if not _patched:
        return

    ssl.SSLSocket.do_handshake = _original_do_handshake
    _original_do_handshake = None

    _patched = False
