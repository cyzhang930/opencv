import cv2
import numpy as np
from datetime import datetime
import sys

class Conversion:
    '''
    This class provides methods to convert frames from device output format to rgb for rendering and saving images.
    '''
    # Flag values to denote type of y16 camera.
    OTHER_Y16CAMERAS = 0
    SEE3CAM_20CUG = 1
    SEE3CAM_CU40 = 2

    V4L2_PIX_FMT_Y16 = "Y16 "
    V4L2_PIX_FMT_Y12 = "Y12 "
    format_type = 0
    
    y16CameraFlag = -1  # flag which denotes type of y16 camera.
    y8_frame = None

    @classmethod
    def init_conversion(cls, current_format, device_name):
        '''
        Method Name: init_conversion
        Description: This method enables y16CameraFlag based on the name of the camera, since for each camera, the
                    conversion method is different.
        :param current_format: current output format of the device
        :type current_format: str
        :param device_name: Name of the selected device
        :type device_name:  str
        '''

        cls.format_type, width, height, fps = current_format
        if cls.format_type == cls.V4L2_PIX_FMT_Y16:
            if device_name.find("See3CAM_20CUG") > -1:
                cls.y16CameraFlag = cls.SEE3CAM_20CUG
            elif device_name.find("See3CAM_CU40") > -1:
                cls.y16CameraFlag = cls.SEE3CAM_CU40
            else:
                cls.y16CameraFlag = cls.OTHER_Y16CAMERAS

        cls.y8_frame = np.zeros(shape=(height, width), dtype=np.uint8)

    @classmethod
    def convert_frame(cls, frame, frame_format):
        '''
        Method Name: convert_frame
        Description: This method calls the conversion function based on the frame foramt
        :param frame: frame which needs to be converted
        :type frame: Mat
        :param frame_format: The format of the frame
        :type frame_format: str
        :return: the converted frame
        :rtype: Mat
        '''
        if cls.format_type == "UYVY":
            return cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_UYVY)
        if cls.format_type == "YUY2":
            return cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUY2)

        convert_func = {
            "Y12 ": cls.convert_y12_to_y8,
            "Y16 ": cls.convert_y16_to_rgb,
        }
        func = convert_func.get(frame_format, lambda: "Invalid Selection")
        return func(frame)

    @classmethod
    def convert_y12_to_y8(cls, frame):
        '''
        Method Name: convert_y12_to_y8
        Description: This method converts the y12 frame to y8 frame
        :param frame: frame which needs to be converted
        :type frame: Mat
        :return: the converted frame
        :rtype: Mat
        '''

        raw_bytes = frame.tobytes()#converting two dimensional mat data to byte array
        row, column = frame.shape
        filtered_bytes = np.frombuffer(raw_bytes, dtype=np.uint8)
        filtered_bytes = np.reshape(filtered_bytes, (-1, 3))
        filtered_bytes = np.delete(filtered_bytes,2,1)
        filtered_bytes= np.reshape(filtered_bytes,-1)
        m=0
        for i in range(0, row):
            cls.y8_frame[i,]=filtered_bytes[m:m+column]
            m+=column
        return cls.y8_frame  # Converting back to two dimensional Mat

    @classmethod
    def convert_y16_to_rgb(cls, frame):
        '''
        Method Name: convert_y16_to_rgb
        Description: This method converts y16 rgb or y8 for rendering and saving image.
        :param frame: frame which needs to be converted
        :type frame: Mat
        :return: the converted frame
        :rtype: Mat
        '''

        if cls.y16CameraFlag == cls.SEE3CAM_20CUG:
            return cv2.convertScaleAbs(frame, 0.2490234375)
        elif cls.y16CameraFlag == cls.SEE3CAM_CU40:
            return cls.convert_RGIR_to_RGGB(frame)
        elif cls.y16CameraFlag == cls.OTHER_Y16CAMERAS:
            return cv2.convertScaleAbs(frame, 0.06226)

    @staticmethod
    def convert_y12_for_still(frame):
        '''
        Method Name: convert_y12_for_still
        Description: This method converts the y12 frame to y16 with padding in order to save as raw image.
        :param frame: frame which needs to be converted
        :type frame: Mat
        :return: the converted frame
        :rtype: bytearray
        '''

        raw_bytes = frame.tobytes()
        row, column = frame.shape
        y12_still_buffer = np.zeros(row * column * 2, dtype=np.uint8)
        m = 0
        stride = column * 2
        for j in range(0, row):
            for i in range(0, stride, 4):
                y12_still_buffer[(stride * j) + i + 1] = ((0XF0 & raw_bytes[m]) >> 4)
                bPixel1 = (raw_bytes[m] & 0X0F)
                bPixel2 = (raw_bytes[m + 2] & 0X0F)
                bPixel1 = (bPixel1 << 4)
                y12_still_buffer[(stride * j) + i] = bPixel1 + bPixel2
                y12_still_buffer[(stride * j) + i + 3] = ((0XF0 & raw_bytes[m + 1]) >> 4)
                bPixel1 = (raw_bytes[m + 1] & 0X0F)
                bPixel2 = (raw_bytes[m + 2] & 0XF0)
                bPixel1 = (bPixel1 << 4)
                bPixel2 = (bPixel2 >> 4)
                y12_still_buffer[(stride * j) + i + 2] = bPixel1 + bPixel2
                m += 3
        return y12_still_buffer

    @staticmethod
    def convert_RGIR_to_RGGB(frame):
        '''
        Method Name: convert_RGIR_to_RGGB
        Description: This method converts RGIR to RGGB frame using nearby neighbour interpolation method
                     and seperates the IR frame
        :param frame: frame which needs to be converted
        :type frame: Mat
        :return: the converted frame
        :rtype: rgb frame and IR frame
        '''

        row, column = frame.shape
        bayer_RGIR = cv2.convertScaleAbs(frame, 0.249023)
        bayer_RGGB = bayer_RGIR.clone()

        ir_frame = np.zeros(int((column * row) / 4), np.uint8).reshape(int(row / 2), int(column / 2))

        for i in range(0, row, 2):
            for j in range(0, column, 2):
                bayer_RGGB[i + 1, j] = bayer_RGIR[i, j + 1]
                ir_frame[int(i / 2), int(j / 2)] = bayer_RGIR[i + 1, j]

        rgb_frame = cv2.cvtColor(bayer_RGGB, cv2.COLOR_BayerRG2BGR)
        return rgb_frame, ir_frame

