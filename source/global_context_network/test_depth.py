#!/usr/bin/env python
# Master's Thesis - Depth Estimation by Convolutional Neural Networks
# Jan Ivanecky; xivane00@stud.fit.vutbr.cz

from __future__ import print_function	
import numpy as np
import matplotlib.pyplot as plt
import sys
from PIL import Image
import cv2
import cv
import os.path
os.environ['GLOG_minloglevel'] = '2' 
import caffe
import scipy.ndimage
import argparse
import operator	
import shutil

from eval_depth import Test, PrintTop5, LogDepth

WIDTH = 298
HEIGHT = 218
OUT_WIDTH = 37
OUT_HEIGHT = 27
GT_WIDTH = 420
GT_HEIGHT = 320


def testNet(net, img):	
	net.blobs['X'].data[...] = img	
	net.forward()
	output = net.blobs['depth'].data
	output = np.reshape(output, (1,1,OUT_HEIGHT, OUT_WIDTH))
	return output
	
def loadImage(path, channels, width, height):
	img = caffe.io.load_image(path)
	img = caffe.io.resize(img, (height, width, channels))
	img = np.transpose(img, (2,0,1))
	img = np.reshape(img, (1,channels,height,width))
	return img

def printImage(img, name, channels, width, height):
	params = list()
	params.append(cv.CV_IMWRITE_PNG_COMPRESSION)
	params.append(8)

	imgnp = np.reshape(img, (height,width, channels))
	imgnp = np.array(imgnp * 255, dtype = np.uint8)
	cv2.imwrite(name, imgnp, params)

def eval(out, gt, rawResults):
		linearGT = gt * 10.0
		linearOut = out * 10.0
		rawResults = [x + y for x, y in zip(rawResults, Test(linearOut, linearGT))]
		return rawResults

def ProcessToOutput(depth):
	depth = np.clip(depth, 0.001, 1000)	
	return np.clip(2 * 0.179581 * np.log(depth) + 1, 0, 1)
			
caffe.set_mode_cpu()

parser = argparse.ArgumentParser()
parser.add_argument("input_dir", help="directory with input images")
parser.add_argument("gt_dir", help="directory with ground truth files")
parser.add_argument("output", help="folder to output to")
parser.add_argument("snaps", help="folder with snapshots to use")
parser.add_argument('--log', action='store_true', default=False)
args = parser.parse_args()

try:
	os.mkdir(args.output)
except OSError:
	print ('Output directory already exists, not creating a new one')
try:
	os.mkdir(args.output + "_abs")
except OSError:
	print ('Output directory already exists, not creating a new one')
fileCount = len([name for name in os.listdir(args.input_dir)])

results = [dict() for x in range(10)]
for snapshot in os.listdir(args.snaps):
	if not snapshot.endswith("caffemodel"):
		continue
	currentSnapDir = snapshot.replace(".caffemodel","")
	if os.path.exists(args.output + "/" + currentSnapDir):
		shutil.rmtree(args.output + "/" + currentSnapDir)
	if os.path.exists(args.output + "_abs/" + currentSnapDir):
		shutil.rmtree(args.output + "_abs/" + currentSnapDir)
	os.mkdir(args.output + "/" + currentSnapDir)
	os.mkdir(args.output + "_abs/" + currentSnapDir)
	print(currentSnapDir)
	sys.stdout.flush()
	netFile = snapshot.replace(".caffemodel",".prototxt")
	net = caffe.Net(args.snaps + '/' + netFile, args.snaps + '/' + snapshot, caffe.TEST)
	
	
	rawResults = np.zeros((10))
	for count, file in enumerate(os.listdir(args.input_dir)):
		out_string = str(count) + '/' + str(fileCount) + ': ' + file
		sys.stdout.write('%s\r' % out_string)
		sys.stdout.flush()
	
		inputFileName = file
		inputFilePath = args.input_dir + '/' + inputFileName
		gtFileName = file.replace('colors', 'depth')	
		gtFilePath = args.gt_dir + '/' + gtFileName
	
		gt = loadImage(gtFilePath, 1, GT_WIDTH, GT_HEIGHT)
		input = loadImage(inputFilePath, 3, WIDTH, HEIGHT)	
				
		input *= 255
		input -= 127

		output = testNet(net, input)
		if args.log:
			output = np.exp((output - 1) / 0.179581)

		outWidth = OUT_WIDTH
		outHeight = OUT_HEIGHT
		scaleW = float(GT_WIDTH) / float(OUT_WIDTH)
		scaleH = float(GT_HEIGHT) / float(OUT_HEIGHT)
		output = scipy.ndimage.zoom(output, (1,1,scaleH,scaleW), order=3)
		outWidth *= scaleW
		outHeight *= scaleH

		rawResults = eval(output, gt, rawResults)

		input += 127
		input = input / 255.0
		input = np.transpose(input, (0,2,3,1))
		input = input[:,:,:,(2,1,0)]

		absOutput = output.copy()

		output -= output.mean()
		output /= output.std()

		output *= gt.std()
		output += gt.mean()

		gt = ProcessToOutput(gt)
		output = ProcessToOutput(output)
		absOutput = ProcessToOutput(absOutput)


	
		filename = os.path.splitext(os.path.basename(inputFileName))[0]
		filePath = args.output + '/' + currentSnapDir + '/' + filename + '.png'
		filePathAbs = args.output + '_abs/' + currentSnapDir + '/' + filename + '.png'
		printImage(input, filePath, 3, WIDTH, HEIGHT)
		printImage(input, filePathAbs, 3, WIDTH, HEIGHT)
		printImage(output, filePath.replace('_colors','_depth'), 1, outWidth, outHeight)
		printImage(absOutput, filePathAbs.replace('_colors','_depth'), 1, outWidth, outHeight)
		printImage(gt, filePath.replace('_colors', '_gt'), 1, outWidth, outHeight)
		printImage(gt, filePathAbs.replace('_colors', '_gt'), 1, outWidth, outHeight)
			
	
	rawResults[:] = [x / fileCount for x in rawResults]
	
	
	for i in xrange(10):
		results[i][currentSnapDir] = rawResults[i]
		
titles = ["AbsRelDiff", "SqrRelDiff", "RMSE", "RMSELog", "SIMSE", "Log10", "MVN", "Threshold 1.25","Threshold 1.25^2", "Threshold 1.25^3"]
for i in xrange(10):
		results[i] = sorted(results[i].items(), key=operator.itemgetter(1))
		if i > 6:
			results[i] = list(reversed(results[i]))
		PrintTop5(titles[i], results[i])
