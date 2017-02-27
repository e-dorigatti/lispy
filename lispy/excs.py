
class LispyException(Exception):
    def __init__(self, msg, **details):
        self.msg = msg
        self.details = details

    def __str__(self):
        msg = (' ' + self.msg) if self.msg else ''
        details = (' ' + str(self.details)) if self.details else ''
        return '%s:%s%s' % (self.__class__.__name__, msg, details)


class NameNotFoundException(LispyException):
    def __init__(self, name):
        super(NameNotFoundException, self).__init__(
            'Name not found', name=name
        )


class SyntaxErrorException(LispyException):
    def __init__(self, msg, **details):
        super(SyntaxErrorException, self).__init__(
            msg, **details
        )
