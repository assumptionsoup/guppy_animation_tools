'''
A very basic observer pattern implementation.

*******************************************************************************
    License and Copyright
    Copyright 2011-2017 Jordan Hueckstaedt
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.


'''

from guppy_animation_tools.utils import decorator
from guppy_animation_tools import getLogger


_log = getLogger(__name__)


class BaseMessage(object):
    '''
    A simple message for an observer system
    '''
    def __init__(self, data=None):
        self.data = data
        self.id = type(self).__name__

        # Injected onto message from dispatcher
        self.owner = None


@decorator.memoized
def MessageFactory(id_):
    '''
    Create a simple message class based on the string ID given.

    This allows for simple messages (ones that only compare id's)
    and complex ones (ones that compare instances and class names)
    '''
    if not isinstance(id_, basestring):
        raise TypeError("Can only create message from string id's")
    if not id_[0].isalpha():
        raise TypeError("Message must start with an alphabet character")

    class CustomMessage(BaseMessage):
        def __init__(self, data=None):
            super(CustomMessage, self).__init__(data=data)
            # ID is never mangled for simplistic type checking
            self.id = id_

    # class name is mangled to keep it pythonic
    CustomMessage.__name__ = id_.replace(' ', '_')
    return type(id_, tuple([BaseMessage]), {})


class Observer(object):
    '''
    A base observer class.

    Objects wishing to receive a message do not have to inherit from
    this class - they just have to implement this interface.
    '''
    def receiveMessage(self, message):
        pass


class Dispatcher(object):
    '''
    This is the "subject" in this simple observer system.

    Named "Dispatcher" instead because "Subject" is a super
    generic and confusing if you're not intimately familiar with
    observer patterns
    '''
    def __init__(self):
        self._observers = []

    def addObserver(self, other):
        try:
            # Test that observer implements the Observer interface
            other.receiveMessage
        except AttributeError:
            raise TypeError("%s does not implement the observer interface." %
                            type(other))

        self._observers.append(other)

    def removeObserver(self, other):
        self._observers.remove(other)

    def send(self, owner, message, data=None):
        if not isinstance(message, BaseMessage):
            message = MessageFactory(message)(data=data)

        if message.owner is not None:
            raise TypeError("Messages can only be sent once per instance!")

        message.owner = owner
        _log.debug("Sending message: %s", message.id)

        # This is currently a very simplistic observer system.
        # No error checking here. Messages will not continue
        # if an error occurs.
        for observer in self._observers:
            observer.receiveMessage(message)


class MessageBlocker(object):
    def __init__(self, observer, dispatcher):
        self.observer = observer
        self.dispatcher = dispatcher
        self._hadObserver = False

    def __enter__(self):
        try:
            self.dispatcher.removeObserver(self.observer)
        except ValueError:
            pass
        else:
            self._hadObserver = True
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if self._hadObserver:
            self.dispatcher.addObserver(self.observer)
