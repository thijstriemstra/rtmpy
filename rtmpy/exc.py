# Copyright (c) The RTMPy Project.
# See LICENSE.txt for details.

"""
RTMPy exception types.

@since: 0.1
"""


class NetConnectionError(Exception):
    """
    """


class CallFailed(NetConnectionError):
    """
    """

    code = 'NetConnection.Call.Failed'


class ConnectError(NetConnectionError):
    """
    """


class ConnectFailed(ConnectError):
    """
    """

    code = 'NetConnection.Connect.Failed'


class ConnectRejected(ConnectError):
    """
    """

    code = 'NetConnection.Connect.Rejected'


class InvalidApplication(NetConnectionError):
    """
    """

    code = 'NetConnection.Connect.InvalidApp'