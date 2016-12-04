# coding: utf8
# auto: flytrap
import sys
import logging
import StringIO
import socket
import tornado.ioloop
import tornado.web
import tornado.websocket

PORT = 9002
io_instance = tornado.ioloop.IOLoop.instance()

logger = logging.getLogger('web_socket')
logger.setLevel(logging.INFO)
log_format = logging.Formatter('%(levelname)s - %(message)s')
stream_handle = logging.StreamHandler(sys.stdout)
stream_handle.setFormatter(log_format)
logger.addHandler(stream_handle)


class ConnectException(Exception):
    pass


class Banner:
    version = 0
    length = 0
    pid = 0
    realWidth = 0
    realHeight = 0
    virtualWidth = 0
    virtualHeight = 0
    orientation = 0
    quirks = 0


class StreamDemo(object):
    def __init__(self, port):
        self.readBannerBytes = 0
        self.bannerLength = 2
        self.readFrameBytes = 0
        self.frameBodyLength = 0
        self.frameBody = StringIO.StringIO()
        self.banner = Banner
        self.socket = socket.socket()
        try:
            self.socket.connect(('0.0.0.0', port))
        except socket.error:
            raise ConnectException('')

    def revive_data(self, send_data_func):
        chunk = self.socket.recv(1024)
        chunk_len = len(chunk)
        logger.info('chunk(length=%d)' % chunk_len)
        cursor = 0
        read_banner_bytes = 0
        while cursor < chunk_len:
            chunk_cur = chunk[cursor]
            if read_banner_bytes < self.bannerLength:
                byte = read_banner_bytes
                self.check_banner(byte, chunk_cur)
                cursor += 1
                read_banner_bytes += 1
                if (read_banner_bytes == self.bannerLength):
                    print('banner', self.banner)
            elif self.readFrameBytes < 4:
                num = chunk_cur << (self.readFrameBytes * 8)
                self.readFrameBytes += num if num >= 0 else 0
                cursor += 1
                self.readFrameBytes += 1
                logger.info('headerbyte%d(val=%d)', self.readFrameBytes, self.frameBodyLength)
            else:
                if chunk_len - cursor >= self.frameBodyLength:
                    logger.info('bodyfin(len=%d,cursor=%d)', self.frameBodyLength, cursor)
                    self.frameBody = ''.join([self.frameBody, chunk[cursor:cursor + self.frameBodyLength]])
                    if self.frameBody[0] != 0xFF or self.frameBody[1] != 0xD8:
                        logger.error('Frame body does not start with JPG header %s' % self.frameBody)
                        io_instance.stop()
                    send_data_func(self.frameBody)
                    cursor += self.frameBodyLength
                    self.frameBodyLength = self.readFrameBytes = 0
                    self.frameBody = ''
                else:
                    logger.info('body(len=%d)', chunk_len - cursor)
                    self.frameBody = ''.join([self.frameBody, chunk[cursor:chunk_len]])
                    self.frameBodyLength -= chunk_len - cursor
                    self.readFrameBytes += chunk_len - cursor
                    cursor = chunk_len

    def check_banner(self, byte, chunk_cur):
        if byte == 0:
            self.banner.version = chunk_cur
        elif byte == 1:
            self.banner.length = self.bannerLength = chunk_cur
        elif byte <= 21:
            sub = (byte - 2) / 4 * 4 + 2
            num = chunk_cur << ((byte - sub) * 8)
            num = num if num >= 0 else 0
            if byte in [2, 3, 4, 5]:
                self.banner.pid += num
            elif byte in [6, 7, 8, 9]:
                self.banner.realWidth += num
            elif byte in [10, 11, 12, 13]:
                self.banner.realHeight += num
            elif byte in [14, 15, 16, 17]:
                self.banner.virtualWidth += num
            elif byte in [18, 19, 20, 21]:
                self.banner.virtualHeight += num
        elif byte == 22:
            self.banner.orientation += chunk_cur * 90
        elif byte == 23:
            self.banner.quirks = chunk_cur

    def end(self):
        try:
            self.socket.close()
        except:
            pass


class Index(tornado.web.RequestHandler):
    def get(self):
        # logger.info('index get')
        self.render('index.html')


class WebSocketDemo(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        logger.info(origin)
        return True

    def open(self):
        logger.info('Got a client')
        try:
            self.my_stream = StreamDemo(1717)
        except ConnectException:
            logger.error('Be sure to run `adb forward tcp:1717 localabstract:minicap`')
            io_instance.stop()

    def on_message(self, message):
        if hasattr(self, 'my_stream'):
            self.my_stream.revive_data(self.write)

    def on_close(self):
        logger.info('Lost a client')
        if hasattr(self, 'my_stream'):
            self.my_stream.end()


if __name__ == '__main__':
    app = tornado.web.Application([
        ('/', Index),
        ('/minicap', WebSocketDemo),
    ])
    app.listen(PORT)
    logger.info('Listening on port %d' % PORT)
    io_instance.start()
