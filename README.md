# apertium-weights-learner

This is a python3 script that can be used for transfer weights training (see http://wiki.apertium.org/wiki/Ideas_for_Google_Summer_of_Code/Weighted_transfer_rules).

## Prerequisites
To run this version of transfer weights training for a given language pair, you need:
* source and target language corpora (they don't have to be parallel to each other)
* apertium with the language pair of interest
* kenlm (https://kheafield.com/code/kenlm/)

## Get the corpora
The corpora can be obtained from http://www.statmt.org/wmt12/translation-task.html

## Prepare language model
You need to make a language model for your target language.

* First, take a big corpus, tokenize and normalize it using tools/simpletok.py script:
```
cd tools
./simpletok.py INPUT_FILE OUTPUT_FILE
```
* Alternatively, if you have your corpus in a number of separate files (which would be the case with. e.g., news crawl corpora from http://www.statmt.org/wmt12/translation-task.html), you can run tools/glue.py to simultaneously normalize and glue all the files together:
```
cd tools
./glue.py INPUT_DIRECTORY OUTPUT_FILE
```
* After that, you are ready to train language model. Cd into build directory of your kenlm installation and run:
```
bin/lmplz -o 5 -T FOLDER_FOR_TMP_FILE <CORPUS_FILE >MODEL_NAME.arpa
```
Be advised that you might need disk space for your language model rougly 15 times of the corpus volume.
* It is highly recommended that you compile a binary after that as it works significantly faster:
```
bin/build_binary -T FOLDER_FOR_TMP_FILE MODEL_NAME.arpa MODEL_NAME.mmap
```
Be advised that you might need disk space for your language model rougly half of the arpa file volume.

## Run training
* Edit configuration file twlconfig.py, which is self-explanatory.
* Run training script:
```
./twlearner.py
```

## Known issues
So far, learner script runs out of memory or something at approx. 7500 input lines while looking for ambiguous sentences and translating them and gets killed by the system.
