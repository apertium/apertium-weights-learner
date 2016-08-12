#! /usr/bin/python3

import os, sys
import simpletok

if len(sys.argv) != 3:
    print("Please specify input folder and output file name:")
    print("./glue INPUT_FOLDER OUTPUT_FILE")
else:
    main_dir = sys.argv[1]
    fnames = os.listdir(main_dir)
    fnames.sort()
    with open(sys.argv[2], 'w', encoding='utf-8') as ofile: 
        for ifname in fnames:
            with open(os.path.join(main_dir, ifname), 'r', encoding='utf-8') as ifile:
                for line in ifile:
                    ofile.write(simpletok.normalize(line))
            ofile.write('\n')
