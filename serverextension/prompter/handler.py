"""
jupyter has no native mechanism for thread-safe access to the kernel

this is a hack to get around that by adding in our own locks
"""

from notebook.services.kernels.handlers import ZMQChannelsHandler
from tornado import gen
from threading import RLock

class TSChannelHandler(ZMQChannelsHandler):

    def initialize(self):
        super(TSChannelHandler, self).initialize()

        if not hasattr(self.application, "kernel_locks"):
            self.application.kernel_locks = {}

    def on_message(self, msg):
        self.log.debug(
            "TSChannel Handler on msg waiting to acquire lock for {0}".format(self.kernel_id))
        self.application.kernel_locks[self.kernel_id].acquire()
        super(TSChannelHandler, self).on_message(msg)
#        print(
#            "TSChannel Handler on msg releasing lock for {0}".format(self.kernel_id))
#        self.application.kernel_locks[self.kernel_id].release()


    def _on_zmq_reply(self, stream, msg):
        super(TSChannelHandler, self)._on_zmq_reply(stream, msg)
        self.log.debug("TSChannelHandler on zmq reply relinquishing lock for {0}".format(self.kernel_id))
        try:
            self.application.kernel_locks[self.kernel_id].release()
        except RuntimeError:
            # then lock already released
            pass

    def open(self, kernel_id):
        if kernel_id not in self.application.kernel_locks:
            self.application.kernel_locks[kernel_id] = RLock()
            print("added lock for kernel {0}".format(kernel_id))
        print(
            "TSChannel Handler open waiting to acquire lock for {0}".format(self.kernel_id))
        self.application.kernel_locks[self.kernel_id].acquire()
        super(TSChannelHandler, self).open(kernel_id)
        print(
            "TSChannel Handler open releasing lock for {0}".format(self.kernel_id))
        self.application.kernel_locks[self.kernel_id].release()
