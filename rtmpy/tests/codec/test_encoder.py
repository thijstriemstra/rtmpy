# Copyright (c) 2007-2009 The RTMPy Project.
# See LICENSE for details.

"""
Encoding tests for L{rtmpy.rtmp.codec}.
"""

from twisted.trial import unittest

from rtmpy.rtmp import codec, interfaces
from rtmpy import util
from rtmpy.tests.util import DummyChannelManager, DummyChannel, DummyHeader


class BaseEncoderTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        self.manager = DummyChannelManager()
        self.encoder = codec.Encoder(self.manager)
        self.buffer = util.BufferedByteStream()

        self.encoder.registerConsumer(self.buffer)


class ClassContextTestCase(BaseEncoderTestCase):
    """
    Tests for L{codec.ChannelContext}.
    """

    def setUp(self):
        BaseEncoderTestCase.setUp(self)

        self.channel = DummyChannel()
        self.context = codec.ChannelContext(self.channel, self.encoder)
        self.buffer = self.context.buffer

    def test_init(self):
        self.assertIdentical(self.context.channel, self.channel)
        self.assertIdentical(self.context.encoder, self.encoder)

        self.assertTrue(isinstance(self.context.buffer, util.BufferedByteStream))
        self.assertFalse(self.context.active)
        self.assertEquals(self.context.header, None)

        self.assertIdentical(self.context, self.channel.consumer)

    def test_write(self):
        self.assertFalse(self.context.active)
        self.assertEquals(self.buffer.tell(), 0)

        self.encoder.activeChannels = set([self.channel])
        self.encoder.channelContext = {self.channel: self.context}

        self.context.write('hello')
        self.assertTrue(self.context.active)
        self.assertEquals(self.buffer.getvalue(), 'hello')
        self.assertEquals(self.buffer.tell(), 5)

        self.assertEquals(self.encoder.activeChannels, set([self.channel]))

    def test_getRelativeHeader(self):
        h = DummyHeader(relative=False, channelId=3, bodyLength=50,
            timestamp=10)
        self.channel.setHeader(h)

        self.assertIdentical(self.context.getRelativeHeader(), h)
        self.assertIdentical(self.context.header, None)

        self.context.header = DummyHeader(relative=False, channelId=3,
            bodyLength=10, timestamp=2)

        h = self.context.getRelativeHeader()

        self.assertTrue(interfaces.IHeader.providedBy(h))
        self.assertTrue(h.relative)


class GetDataTestCase(BaseEncoderTestCase):
    """
    Tests for L{codec.ChannelContext.getData}
    """

    def setUp(self):
        BaseEncoderTestCase.setUp(self)

        self.channel = DummyChannel()
        self.context = codec.ChannelContext(self.channel, self.encoder)
        self.context.active = True
        self.encoder.channelContext = {self.channel: self.context}
        self.buffer = self.context.buffer

        self.encoder.activeChannels = [self.channel]

    def test_empty(self):
        self.assertEquals(self.buffer.getvalue(), '')
        self.assertEquals(self.context.getData(1), None)
        self.assertFalse(self.context.active)
        self.assertEquals(self.encoder.activeChannels, [])

    def test_read(self):
        self.buffer.write('foobar')
        self.buffer.seek(0)

        self.assertEquals(self.context.getData(1), 'f')
        self.assertEquals(self.buffer.getvalue(), 'oobar')
        self.assertTrue(self.context.active)
        self.assertEquals(self.encoder.activeChannels, [self.channel])

    def test_under(self):
        self.buffer.write('foobar')
        self.buffer.seek(2)

        self.assertEquals(self.context.getData(10), None)
        self.assertEquals(self.buffer.getvalue(), 'foobar')
        self.assertFalse(self.context.active)
        self.assertEquals(self.encoder.activeChannels, [])
        self.assertEquals(self.buffer.tell(), 2)


class EncoderTestCase(BaseEncoderTestCase):
    """
    Tests for L{codec.Encoder}
    """

    def test_init(self):
        self.assertEquals(self.encoder.channelContext, {})
        self.assertEquals(self.encoder.activeChannels, set())
        self.assertEquals(self.encoder.currentContext, None)

    def test_job(self):
        self.assertEquals(self.encoder.getJob(), self.encoder.encode)

    def test_registerConsumer(self):
        consumer = object()

        self.encoder.registerConsumer(consumer)
        self.assertIdentical(consumer, self.encoder.consumer)

        otherConsumer = object()

        self.encoder.registerConsumer(otherConsumer)
        self.assertIdentical(otherConsumer, self.encoder.consumer)

    def test_activateChannel(self):
        channel = DummyChannel()

        self.assertFalse(channel in self.encoder.channelContext.keys())
        self.assertFalse(channel in self.encoder.activeChannels)

        e = self.assertRaises(RuntimeError, self.encoder.activateChannel, channel)
        self.assertEquals(str(e), 'Attempted to activate a non-existant channel')

        self.encoder.channelContext = {channel: 'foo'}
        self.assertFalse(channel in self.encoder.activeChannels)

        self.encoder.activateChannel(channel)
        self.assertTrue(channel in self.encoder.activeChannels)

    def test_deactivateChannel(self):
        channel = DummyChannel()

        self.assertFalse(channel in self.encoder.channelContext.keys())
        self.assertFalse(channel in self.encoder.activeChannels)

        e = self.assertRaises(RuntimeError, self.encoder.deactivateChannel, channel)
        self.assertEquals(str(e), 'Attempted to deactivate a non-existant channel')

        context = codec.ChannelContext(channel, self.encoder)

        self.encoder.channelContext[channel] = context
        self.encoder.activeChannels.update([channel])

        self.assertTrue(channel in self.encoder.channelContext.keys())
        self.assertTrue(channel in self.encoder.activeChannels)

        self.encoder.deactivateChannel(channel)
        self.assertFalse(channel in self.encoder.activeChannels)