import sys, re
from subprocess import Popen, PIPE

# apertium special symbols for removal 
apertium_re = re.compile(r'[@#~*]')

class partialTranslator():
    """
    Wrapper for part of Apertium pipeline
    going from bidix lookup to the generation.
    """
    def __init__(self, tixfname, binfname):
        """
        On initialization, partial Apertium pipeline
        is invoked with '-z' option (null flush)
        and remains active waiting for input.
        """
        self.autobil = Popen(['lt-proc', '-b', '-z', 
                              binfname + '.autobil.bin'
                             ],
                             stdin = PIPE, stdout = PIPE)
        self.transfer = Popen(['apertium-transfer', '-b', '-z', 
                               tixfname + '.t1x', 
                               binfname + '.t1x.bin'
                              ], 
                              stdin = self.autobil.stdout, stdout = PIPE)
        self.interchunk = Popen(['apertium-interchunk', '-z',
                                 tixfname + '.t2x',
                                 binfname + '.t2x.bin'
                                ],
                                stdin = self.transfer.stdout, stdout = PIPE)
        self.postchunk = Popen(['apertium-postchunk', '-z',
                                tixfname + '.t2x',
                                binfname + '.t2x.bin'
                               ],
                               stdin = self.interchunk.stdout, stdout = PIPE)
        self.autogen = Popen(['lt-proc', '-g', '-z',
                              binfname + '.autogen.bin'
                             ],
                             stdin = self.postchunk.stdout, stdout = PIPE)

    def translate(self, string):
        """
        Convert input string to bytes,
        send it to the pipeline,
        return the result converted to utf-8.
        """
        string = string.strip() + '[][\n]'

        if type(string) == type(''): 
            bstring = bytes(string, 'utf-8')
        else:
            bstring = string  

        self.autobil.stdin.write(bstring)
        self.autobil.stdin.write(b'\0')
        self.autobil.stdin.flush()

        char = self.autogen.stdout.read(1)
        output = []
        while char and char != b'\0':
            output.append(char)
            char = self.autogen.stdout.read(1)

        return apertium_re.sub('', (b''.join(output)).decode('utf-8').replace('[][\n]',''))

class weightedPartialTranslator():
    """
    Wrapper for part of Apertium pipeline
    going from bidix lookup to the generation.
    It is missing 1st-stage transfer at init,
    because transfer is invoked at translation
    with provided weights file.
    """
    def __init__(self, tixfname, binfname):
        """
        On initialization, fragments of Apertium pipeline
        are invoked with '-z' option (null flush)
        and remain active waiting for input.
        """
        self.tixfname = tixfname
        self.binfname = binfname

        self.autobil = Popen(['lt-proc', '-b', '-z', 
                              binfname + '.autobil.bin'
                             ],
                             stdin = PIPE, stdout = PIPE)

        # transfer is missing here
        # it is invoked during translation
        # using provided transfer weights file 

        self.interchunk = Popen(['apertium-interchunk', '-z',
                                 tixfname + '.t2x',
                                 binfname + '.t2x.bin'
                                ],
                                stdin = PIPE, stdout = PIPE)
        self.postchunk = Popen(['apertium-postchunk', '-z',
                                tixfname + '.t2x',
                                binfname + '.t2x.bin'
                               ],
                               stdin = self.interchunk.stdout, stdout = PIPE)
        self.autogen = Popen(['lt-proc', '-g', '-z',
                              binfname + '.autogen.bin'
                             ],
                             stdin = self.postchunk.stdout, stdout = PIPE)

    def translate(self, string, wixfname):
        """
        Convert input string to bytes,
        send it to the pipeline,
        return the result converted to utf-8.
        """
        string = string.strip() + '[][\n]'

        if type(string) == type(''): 
            bstring = bytes(string, 'utf-8')
        else:
            bstring = string  

        # start going through null flush pipeline
        self.autobil.stdin.write(bstring)
        self.autobil.stdin.write(b'\0')
        self.autobil.stdin.flush()

        char = self.autobil.stdout.read(1)
        autobil_output = []
        while char and char != b'\0':
            autobil_output.append(char)
            char = self.autobil.stdout.read(1)

        # make weighted transfer
        transfer = Popen(['apertium-transfer', '-bw',
                          wixfname,
                          self.tixfname + '.t1x', 
                          self.binfname + '.t1x.bin'
                         ],
                         stdin = PIPE, stdout = PIPE)

        transfer_output, err = transfer.communicate(b''.join(autobil_output))

        # resume going through null flush pipeline
        self.interchunk.stdin.write(transfer_output)
        self.interchunk.stdin.write(b'\0')
        self.interchunk.stdin.flush()

        char = self.autogen.stdout.read(1)
        autogen_output = []
        while char and char != b'\0':
            autogen_output.append(char)
            char = self.autogen.stdout.read(1)

        return apertium_re.sub('', (b''.join(autogen_output)).decode('utf-8').replace('[][\n]',''))
