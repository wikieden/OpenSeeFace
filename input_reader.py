import re
import sys
import os
import cv2
import numpy as np
import escapi
import dshowcapture
import time
import traceback

class VideoReader():
    def __init__(self, capture, camera=False):
        if os.name == 'nt' and camera:
            self.cap = cv2.VideoCapture(capture, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(capture)
        if self.cap is None:
            print("The video source cannot be opened")
            sys.exit(0)
    def is_open(self):
        return self.cap.isOpened()
    def is_ready(self):
        return True
    def read(self):
        return self.cap.read()
    def close(self):
        self.cap.release()

class EscapiReader(VideoReader):
    def __init__(self, capture, width, height, fps):
        self.device = None
        self.width = width
        self.height = height
        self.fps = fps
        self.device = capture
        self.buffer = escapi.init_camera(self.device, self.width, self.height, self.fps)
        escapi.do_capture(self.device)
    def is_open(self):
        return True
    def is_ready(self):
        return escapi.is_capture_done(self.device)
    def read(self):
        if escapi.is_capture_done(self.device):
            image = escapi.read(self.device, self.width, self.height, self.buffer)
            escapi.do_capture(self.device)
            return True, image
        else:
            return False, None
    def close(self):
        escapi.deinit_camera(self.device)

class DShowCaptureReader(VideoReader):
    def __init__(self, capture, width, height, fps, use_dshowcapture=True):
        self.device = None
        self.width = width
        self.height = height
        self.fps = fps
        self.device = dshowcapture.DShowCapture()
        self.device.get_devices()
        self.device_name = self.device.get_device(capture)
        self.device.capture_device(capture, self.width, self.height, self.fps)
        self.timeout = 1000
    def is_open(self):
        return self.device.capturing()
    def is_ready(self):
        return self.device.capturing()
    def read(self):
        img = self.device.get_frame(self.timeout)
        if img is None:
            return False, None
        else:
            return True, img
    def close(self):
        self.device.destroy_capture()

class OpenCVReader(VideoReader):
    def __init__(self, capture, width, height, fps):
        self.device = None
        self.width = width
        self.height = height
        self.fps = fps
        super(OpenCVReader, self).__init__(capture, camera=True)
        self.cap.set(3, width)
        self.cap.set(4, height)
    def is_open(self):
        return super(OpenCVReader, self).is_open()
    def is_ready(self):
        return super(OpenCVReader, self).is_ready()
    def read(self):
        return super(OpenCVReader, self).read()
    def close(self):
        super(OpenCVReader, self).close()

class RawReader:
    def __init__(self, width, height):
        self.width = int(width)
        self.height = int(height)
        
        if self.width < 1 or self.height < 1:
            print("No acceptable size was given for reading raw RGB frames.")
            sys.exit(0)

        self.len = self.width * self.height * 3
        self.open = True
    def is_open(self):
        return self.open
    def is_ready(self):
        return True
    def read(self):
        frame = bytearray()
        read_bytes = 0
        while read_bytes < self.len:
            bytes = sys.stdin.buffer.read(self.len)
            read_bytes += len(bytes)
            frame.extend(bytes)
        return True, np.frombuffer(frame, dtype=np.uint8).reshape((self.height, self.width, 3))
    def close(self):
        self.open = False

def try_int(s):
    try:
        return int(s)
    except:
        return None

def test_reader(reader):
    got_any = False
    try:
        for i in range(30):
            if not reader.is_ready():
                time.sleep(0.02)
            ret, frame = reader.read()
            if not ret:
                time.sleep(0.02)
                print("No frame")
            else:
                print("Got frame")
                got_any = True
        if reader.is_open():
            return got_any
        print("Fail")
        return False
    except:
        traceback.print_exc()
        print("Except")
        return False

class InputReader():
    def __init__(self, capture, raw_rgb, width, height, fps, use_dshowcapture=False):
        self.reader = None
        try:
            if raw_rgb > 0:
                self.reader = RawReader(width, height)
            elif os.path.exists(capture):
                self.reader = VideoReader(capture)
            elif capture == str(try_int(capture)):
                if os.name == 'nt':
                    # Try with DShowCapture
                    good = True
                    name = ""
                    try:
                        if use_dshowcapture:
                            self.reader = DShowCaptureReader(int(capture), width, height, fps)
                            name = self.reader.device_name
                            good = test_reader(self.reader)
                        else:
                            good = False
                    except:
                        good = False
                    if good:
                        return
                    # Try with Escapi
                    good = True
                    try:
                        print(f"DShowCapture failed. Falling back to escapi for device {name}.", file=sys.stderr)
                        escapi.init()
                        devices = escapi.count_capture_devices()
                        found = None
                        for i in range(devices):
                            escapi_name = str(escapi.device_name(i).decode('utf8'))
                            if name == escapi_name:
                                found = i
                        if found is None:
                            good = False
                        else:
                            print(f"Found device {name} as {i}.", file=sys.stderr)
                            self.reader = EscapiReader(found, width, height, fps)
                            good = test_reader(self.reader)
                    except:
                        good = False
                    if good:
                        return
                    # Try with OpenCV
                    print(f"Escapi failed. Falling back to OpenCV. If this fails, please change your camera settings.", file=sys.stderr)
                    self.reader = OpenCVReader(int(capture), width, height, fps)
                else:
                    self.reader = OpenCVReader(int(capture), width, height, fps)
        except Exception as e:
            print("Error: " + str(e))

        if self.reader is None or not self.reader.is_open():
            print("There was no valid input.")
            sys.exit(0)
    def is_open(self):
        return self.reader.is_open()
    def is_ready(self):
        return self.reader.is_ready()
    def read(self):
        return self.reader.read()
    def close(self):
        self.reader.close()
