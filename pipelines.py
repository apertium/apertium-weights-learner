import sys
from subprocess import Popen, PIPE

class partialTranslator():
    def __init__(self, tixfname, binfname):
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

        return (b''.join(output)).decode('utf-8').replace('[][\n]','')

class weightedPartialTranslator():
    def __init__(self, tixfname, binfname):
        self.tixfname = tixfname
        self.binfname = binfname

        self.autobil = Popen(['lt-proc', '-b', '-z', 
                              binfname + '.autobil.bin'
                             ],
                             stdin = PIPE, stdout = PIPE)

        # transfer is missing here

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
        # start null flush pipeline
        string = string.strip() + '[][\n]'

        if type(string) == type(''): 
            bstring = bytes(string, 'utf-8')
        else:
            bstring = string  

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

        # resume null flush pipeline
        self.interchunk.stdin.write(transfer_output)
        self.interchunk.stdin.write(b'\0')
        self.interchunk.stdin.flush()

        char = self.autogen.stdout.read(1)
        autogen_output = []
        while char and char != b'\0':
            autogen_output.append(char)
            char = self.autogen.stdout.read(1)

        return (b''.join(autogen_output)).decode('utf-8').replace('[][\n]','')

if __name__ == "__main__":
    t = weightedPartialTranslator('../apertium-en-es/apertium-en-es.en-es', '../apertium-en-es/en-es')

    with open('./tests/testfile.txt', 'r', encoding='utf-8') as ifile:
        for line in ifile:
            print('line:', line)
            mo = t.translate(line, '../apertium-en-es/apertium-en-es.en-es.w1x')
            print('mo:', mo)
            print()
