#!/usr/bin/env python
# encoding: utf-8

import os
import numpy as np
import tensorflow as tf

class VGG():
    def __init__(self, config):
        self.global_step = tf.get_variable('global_step', initializer=0, 
                        dtype=tf.int32, trainable=False)

        self.batch_size = config.batch_size
    
        self.img_width = config.img_width
        self.img_height = config.img_height
        self.img_channel = config.img_channel

        self.start_learning_rate = config.start_learning_rate
        self.decay_rate = config.decay_rate
        self.decay_steps = config.decay_steps


        self.image_holder = tf.placeholder(tf.float32,
                                [self.batch_size, self.img_width, self.img_height, self.img_channel])
        self.label_holder = tf.placeholder(tf.int32, [self.batch_size])
        self.keep_prob = tf.placeholder(tf.float32)


    def print_tensor(self, tensor):
        print tensor.op.name, ' ', tensor.get_shape().as_list()

    def variable_with_weight_loss(self, shape, stddev, wl):
        var = tf.Variable(tf.truncated_normal(shape, stddev=stddev))
        if wl is not None:
            weight_loss = tf.multiply(tf.nn.l2_loss(var), wl, name='weight_loss')
            tf.add_to_collection('losses', weight_loss)
        return var

    def _activation_summary(self, tensor):
        name = tensor.op.name
        tf.summary.histogram(name + '/activatins', tensor)
        tf.summary.scalar(name + '/sparsity', tf.nn.zero_fraction(tensor))

    def conv_layer(self, fm, channels):
        '''
        Arg fm: feather maps
        '''
        shape = fm.get_shape()
        kernel = self.variable_with_weight_loss(shape=[3, 3, shape[-1].value, channels], stddev=1e-2, wl=0.0)
        conv = tf.nn.conv2d(fm, kernel, [1, 1, 1, 1], padding='SAME')
        biases = tf.Variable(tf.constant(0.1, dtype=tf.float32, shape=[channels]))
        pre_activation = tf.nn.bias_add(conv, biases)

        activation = tf.nn.relu(pre_activation)

        self.print_tensor(activation)
        self._activation_summary(activation)

        return activation

    def fc_layer(self, input_op, fan_out):
        '''
        input_op: 输入tensor
        fan_in: 输入节点数
        fan_out： 输出节点数
        '''
        fan_in = input_op.get_shape()[1].value

        weights = self.variable_with_weight_loss(shape=[fan_in, fan_out], stddev=1e-2, wl=0.04)
        biases = tf.Variable(tf.constant(0.1, dtype=tf.float32, shape=[fan_out]))
        pre_activation = tf.nn.bias_add(tf.matmul(input_op, weights), biases)

        activation = tf.nn.relu(pre_activation)

        self.print_tensor(activation)
        self._activation_summary(activation)

        return activation


    def inference(self):
        with tf.name_scope('conv1') as scope:
            conv1_1 = self.conv_layer(self.image_holder, 64)
            conv1_2 = self.conv_layer(conv1_1, 64)
            pool1 = tf.nn.max_pool(conv1_2, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')

        with tf.name_scope('conv2') as scope:
            conv2_1 = self.conv_layer(pool1, 128)
            conv2_2 = self.conv_layer(conv2_1, 128)
            pool2 = tf.nn.max_pool(conv2_2, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')

        with tf.name_scope('conv3') as scope:
            conv3_1 = self.conv_layer(pool2, 256)
            conv3_2 = self.conv_layer(conv3_1, 256)
            conv3_3 = self.conv_layer(conv3_2, 256)
            pool3 = tf.nn.max_pool(conv3_3, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
        
        with tf.name_scope('conv4') as scope:
            conv4_1 = self.conv_layer(pool3, 512)
            conv4_2 = self.conv_layer(conv4_1, 512)
            conv4_3 = self.conv_layer(conv4_2, 512)
            pool4 = tf.nn.max_pool(conv4_3, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')

        with tf.name_scope('conv5') as scope:
            conv5_1 = self.conv_layer(pool4, 512)
            conv5_2 = self.conv_layer(conv5_1, 512)
            conv5_3 = self.conv_layer(conv5_2, 512)
            pool5 = tf.nn.max_pool(conv5_3, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
            self.print_tensor(pool5)


        with tf.name_scope('fc1') as scope:
            reshape = tf.reshape(pool5, [self.batch_size, -1])
            self.print_tensor(reshape)
            fc1 = self. fc_layer(reshape, 4096)
            drop1 = tf.nn.dropout(fc1, self.keep_prob)

        with tf.name_scope('fc2') as scope:
            fc2 = self.fc_layer(drop1, 4096)
            drop2 = tf.nn.dropout(fc2, self.keep_prob)

        with tf.name_scope('final_fc') as scope:
            logits = self.fc_layer(drop2, 20)

        self.print_tensor(logits)

        return logits

    def loss(self, logits):
        labels = tf.cast(self.label_holder, tf.int64)

        cross_entropy_sum = tf.nn.sparse_softmax_cross_entropy_with_logits(
            labels=labels, logits=logits, name='cross_entropy_sum')
        cross_entropy = tf.reduce_mean(cross_entropy_sum, name='cross_entropy')

        tf.add_to_collection('losses', cross_entropy)

        total_loss = tf.add_n(tf.get_collection('losses'), name='total_loss')

        tf.summary.scalar(total_loss.op.name + ' (raw)', total_loss)

        return total_loss


    def train_op(self, total_loss):
        learning_rate = tf.train.exponential_decay(self.start_learning_rate, self.global_step, self.decay_steps, self.decay_rate, staircase=True)
        train_op = tf.train.AdamOptimizer(learning_rate).minimize(total_loss, self.global_step)

    def accuracy(self, logits):
        return tf.nn.in_top_k(logits, self.label_holder, 1)