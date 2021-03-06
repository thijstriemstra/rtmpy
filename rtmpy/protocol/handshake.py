# Copyright the RTMPy Project
#
# RTMPy is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# RTMPy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with RTMPy.  If not, see <http://www.gnu.org/licenses/>.

"""
RTMP handshake support.

RTMP handshaking is similar (at least conceptually) to syn/ack handshaking. We
extend this concept. Each 'packet' (syn or ack) consists of a payload of data
which is represented by L{Packet}. It is up to the negotiators (which
generate/decode the packets) to determine if the packets are valid.

@since: 0.1
"""


from zope.interface import implements, Interface, Attribute
from pyamf.util import BufferedByteStream

from rtmpy.protocol import version
from rtmpy import util


HANDSHAKE_LENGTH = 1536



class IProtocolImplementation(Interface):
    """
    Provides a handshake implementation for a specific protocol version of RTMP.
    """

    ClientNegotiator = Attribute(
        'Implements IHandshakeNegotiator for client handshakes')
    ServerNegotiator = Attribute(
        'Implements IHandshakeNegotiator for server handshakes')



class IHandshakeObserver(Interface):
    """
    Observes handshake events.
    """

    def handshakeSuccess(data):
        """
        Handshaking was successful. C{data} will contain any unconsumed bytes
        from the handshaking process.
        """



class IHandshakeNegotiator(Interface):
    """
    Negotiates handshakes.
    """

    observer = Attribute("An L{IHandshakeObserver} that listens for events "
        "from this negotiator")
    transport = Attribute("Provides ITransport")


    def start(uptime=None, version=None):
        """
        Called to start the handshaking process. You can supply the uptime and
        version, otherwise they will be worked out automatically. The version
        specifically will be set to enable H.264 streaming.
        """


    def dataReceived(data):
        """
        Called when handshaking data has been received.
        """


    def buildSynPayload():
        """
        Builds the handshake payload for the negotiators syn payload (the first
        packet sent).
        """


    def buildAckPayload():
        """
        Builds the handshake payload for the negotiators ack payload (the second
        packet sent).
        """



class HandshakeError(Exception):
    """
    Generic class for handshaking related errors.
    """



class VerificationError(HandshakeError):
    """
    Raised if the handshake verification failed.
    """



class Packet(object):
    """
    A handshake packet.

    @ivar uptime: The uptime of the system in milliseconds. This value seems
        fairly arbitrary at this point. First 4 bytes of the packet.
    @type uptime: 32bit unsigned int.
    @ivar version: The version of the peer. For non-digested handshaking this
        will be 0. The second 4 bytes of the packet.
    @type version: 32bit unsigned int.
    @ivar payload: A blob of data which makes up the rest of the packet. This
        must be C{HANDSHAKE_LENGTH} - 8 bytes in length.
    @type payload: C{str}
    """

    def __init__(self, uptime=0, version=0):
        self.uptime = uptime
        self.version = version

        self.payload = None


    def encode(self, buffer):
        """
        Encodes this packet to a stream.
        """
        buffer.write_ulong(self.uptime)
        buffer.write_ulong(self.version)

        buffer.write(self.payload)


    def decode(self, buffer):
        """
        Decodes this packet from a stream.
        """
        self.uptime = buffer.read_ulong()
        self.version = buffer.read_ulong()

        self.payload = buffer.read(HANDSHAKE_LENGTH - 8)



class BaseNegotiator(object):
    """
    Base functionality for negotiating an RTMP handshake.

    @ivar observer: An observer for handshake negotiations.
    @type observer: L{IHandshakeObserver}
    @ivar buffer: Any data that has not yet been consumed.
    @type buffer: L{BufferedByteStream}
    @ivar started: Determines whether negotiations have already begun.
    @type started: C{bool}
    @ivar my_syn: The initial handshake packet that will be sent by this
        negotiator.
    @type my_syn: L{Packet}
    @ivar my_ack: The handshake packet that will be sent after the peer has sent
        its syn.
    @ivar peer_syn: The initial L{Packet} received from the peer.
    @ivar peer_ack: The L{Packet} received in acknowledgement of my syn.
    @ivar peer_version: The handshake version that the peer understands.
    """

    implements(IHandshakeNegotiator)


    def __init__(self, observer, transport):
        self.observer = observer
        self.transport = transport
        self.started = False


    def start(self, uptime=None, version=None):
        """
        Called to start the handshaking negotiations.
        """
        if self.started:
            raise HandshakeError('Handshake negotiator cannot be restarted')

        self.started = True
        self.buffer = BufferedByteStream()

        self.peer_version = None

        self.my_syn = Packet(uptime, version)
        self.my_ack = None

        self.peer_syn = None
        self.peer_ack = None

        self.buildSynPayload(self.my_syn)

        self._writePacket(self.my_syn)


    def getPeerPacket(self):
        """
        Attempts to decode a L{Packet} from the buffer. If there is not enough
        data in the buffer then C{None} is returned.
        """
        if self.buffer.remaining() < HANDSHAKE_LENGTH:
            # we're expecting more data
            return

        packet = Packet()

        packet.decode(self.buffer)

        return packet


    def _writePacket(self, packet, stream=None):
        stream = stream or BufferedByteStream()

        packet.encode(stream)

        self.transport.write(stream.getvalue())


    def dataReceived(self, data):
        """
        Called when handshake data has been received. If an error occurs
        whilst negotiating the handshake then C{self.observer.handshakeFailure}
        will be called, citing the reason.

        3 stages of data are received. The handshake version, the syn packet and
        then the ack packet.
        """
        if not self.started:
            raise HandshakeError('Data was received, but negotiator was '
                'not started')

        self.buffer.append(data)

        self._process()


    def _process(self):
        if not self.peer_syn:
            self.peer_syn = self.getPeerPacket()

            if not self.peer_syn:
                return

            self.buffer.consume()

            self.synReceived()

        if not self.peer_ack:
            self.peer_ack = self.getPeerPacket()

            if not self.peer_ack:
                return

            self.buffer.consume()

            self.ackReceived()

        # if we get here then a successful handshake has been negotiated.
        # inform the observer accordingly
        self.observer.handshakeSuccess(self.buffer.getvalue())


    def writeAck(self):
        """
        Writes L{self.my_ack} to the observer.
        """
        self._writePacket(self.my_ack)


    def buildSynPayload(self, packet):
        """
        Called to build the syn packet, based on the state of the negotiations.
        """
        raise NotImplementedError


    def buildAckPayload(self, packet):
        """
        Called to build the ack packet, based on the state of the negotiations.
        """
        raise NotImplementedError


    def synReceived(self):
        """
        Called when the peers syn packet has been received. Use this function to
        do any validation/verification.
        """


    def ackReceived(self):
        """
        Called when the peers ack packet has been received. Use this function to
        do any validation/verification.
        """



class ClientNegotiator(BaseNegotiator):
    """
    Negotiator for client initiating handshakes.
    """


    def synReceived(self):
        """
        Called when the peers syn packet has been received. Use this function to
        do any validation/verification.

        We're waiting for the ack packet to be received before we do anything.
        """


    def ackReceived(self):
        """
        Called when the peers ack packet has been received. Use this function to
        do any validation/verification.

        If validation succeeds then the ack is sent.
        """
        if self.buffer.remaining():
            raise HandshakeError('Unexpected trailing data after peer ack')

        if self.peer_ack.uptime != self.my_syn.uptime:
            raise VerificationError('Received uptime is not the same')

        if self.peer_ack.payload != self.my_syn.payload:
            raise VerificationError('Received payload is not the same')

        self.my_ack = Packet(self.peer_syn.uptime, self.my_syn.version)

        self.buildAckPayload(self.my_ack)

        self.writeAck()



class ServerNegotiator(BaseNegotiator):
    """
    Negotiator for server handshakes.
    """

    def buildSynPayload(self, packet):
        """
        Called to build the syn packet, based on the state of the negotiations.

        C{RTMP} payloads are just random.
        """
        packet.payload = _generate_payload()

    def buildAckPayload(self, packet):
        """
        Called to build the ack packet, based on the state of the negotiations.

        C{RTMP} payloads are just random.
        """
        packet.payload = _generate_payload()


    def synReceived(self):
        """
        Called when the client sends its syn packet.

        Builds and writes the ack packet.
        """
        self.my_ack = Packet(self.peer_syn.uptime, self.my_syn.uptime)

        self.buildAckPayload(self.my_ack)
        self.writeAck()


    def ackReceived(self):
        """
        Called when the clients ack packet has been received.
        """
        if self.my_syn.uptime != self.peer_ack.uptime:
            raise VerificationError('Received uptime is not the same')

        if self.my_syn.payload != self.peer_ack.payload:
            raise VerificationError('Received payload does not match')



def get_implementation(protocol):
    """
    Returns the implementation suitable for handling RTMP handshakes for the
    version specified. Will raise L{HandshakeError} if an invalid version is
    found.

    @param protocol: The C{int} version of the protocol.
    """
    protocol_mod = 'rtmpy.protocol.%s' % (version.get(protocol),)
    full_mod_path = protocol_mod + '.handshake'

    try:
        mod = __import__(full_mod_path, globals(), locals(), [protocol_mod])
    except ImportError:
        raise HandshakeError('Unknown handshake version %r' % (protocol,))

    return mod



def _generate_payload():
    return util.generateBytes(HANDSHAKE_LENGTH - 8)
