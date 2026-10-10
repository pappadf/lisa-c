#!/usr/bin/env python3
"""Serve granny-smith's web build with "/" booting a configured Lisa.

    serve.py WEB_DIR STAGE_DIR PORT QUERY

WEB_DIR is an unpacked granny-smith-web-<version>.zip (web/ + dev_server.py);
its dev_server.py does the serving (cross-origin isolation headers, HTTP/1.1,
port-forwarding quirks).  Files not in web/ come from STAGE_DIR (the floppy,
local media).  "/" answers with a small page that sends the browser on to
index.html?QUERY, so opening the server's address boots the Lisa.  It is a
200 page rather than an HTTP redirect: the GitHub Codespaces port gateway
probes "/" and expects the page itself.
"""
import html
import importlib.util
import os
import sys
from functools import partial
from http.server import ThreadingHTTPServer


def main():
    web, stage, port, query = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    spec = importlib.util.spec_from_file_location('dev_server', os.path.join(web, 'dev_server.py'))
    dev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dev)
    page = ('<!doctype html><meta charset="utf-8"><title>Lisa</title>\n'
            '<p>Starting the Lisa... (<a href="{0}">continue</a>)</p>\n'
            '<script>location.replace({1});</script>\n').format(
                html.escape('index.html?' + query), repr('index.html?' + query)).encode()

    class Handler(dev.Handler):
        def do_GET(self):  # noqa: N802
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return
            super().do_GET()

    Handler.fallback_root = os.path.abspath(stage)
    httpd = ThreadingHTTPServer(('localhost', port),
                                partial(Handler, directory=os.path.join(web, 'web')))
    httpd.daemon_threads = True
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped')


if __name__ == '__main__':
    main()
