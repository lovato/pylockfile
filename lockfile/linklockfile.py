# -*- coding: utf-8 -*-

from __future__ import absolute_import

import time
import os
import os.path
import tempfile
import md5

from . import (LockBase, LockFailed, NotLocked, NotMyLock, LockTimeout,
               AlreadyLocked)

class LinkLockFile(LockBase):
    """Lock access to a file using atomic property of link(2).

    >>> lock = LinkLockFile('somefile')
    >>> lock = LinkLockFile('somefile', threaded=False)
    """

    def __init__(self, path, threaded=False, timeout=None, expires_in=0):

        tmp = tempfile.gettempdir()
        path_hash = md5.new(path).hexdigest()
        lock_file = os.path.join('%s/pylockfile/%s.lock' % (tmp, path_hash) )
        self.expires_in = expires_in
        
        LockBase.__init__(self, path, threaded, timeout, lock_file)
        
        try:
            with open(self.unique_name, "wb") as file:
                file.write("%d" % os.getpid())
        except IOError:
            raise LockFailed("failed to create %s" % self.unique_name)

    def acquire(self, timeout=None, expires_in=None):

        if expires_in is not None:
            self.expires_in = expires_in
        
        timeout = timeout is not None and timeout or self.timeout
        end_time = time.time()
        if timeout is not None and timeout > 0:
            end_time += timeout

        while True:
            
            if not self.is_locked():
                self.break_lock()

            try:
                os.link(self.unique_name, self.lock_file)
            except OSError:
                if timeout is None or timeout <= 0:
                    raise AlreadyLocked("%s is already locked" %
                                        self.path)

                if time.time() > end_time:
                    raise LockTimeout("Timeout waiting to acquire"
                                      " lock for %s" %
                                      self.path)

                time.sleep(1)
            else:
                return

    def release(self):

        # Essa operação tem situação de corrida

        if not self.is_locked():
            self.break_lock()
            return
        elif not self.i_am_locking():
            raise NotMyLock("%s is locked, but not by me" % self.path)
        self.break_lock()

    def is_locked(self):
        if self.is_lock_expired():
            return False
        return os.path.exists(self.lock_file)

    def i_am_locking(self):
        if not self.is_locked():
            return False

        with open(self.lock_file, "r") as file:
            lock_pid = file.read().strip()

        return lock_pid == str(os.getpid()) 

    def break_lock(self):
        if os.path.exists(self.lock_file):
            os.unlink(self.lock_file)

    def get_lock_createtime(self):
        try:
            if os.path.exists(self.lock_file):
                stat = os.stat(self.lock_file)
                return stat.st_ctime
        except:
            pass

        return 0
         
    def get_lock_lifetime(self):
        return time.time() - self.get_lock_createtime()
    
    def is_lock_expired(self):
        if self.expires_in <= 0:
            return False

        create_time = self.get_lock_createtime()
        if create_time == 0:
            return True
        else:
            return self.get_lock_lifetime() > self.expires_in

    def __del__(self):
        if os.path.exists(self.unique_name):
            os.unlink(self.unique_name)
