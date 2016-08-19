# apertium-weights-learner

This is a python3 script that can be used for transfer weights training (see http://wiki.apertium.org/wiki/Ideas_for_Google_Summer_of_Code/Weighted_transfer_rules).

## Prerequisites
To run this version of transfer weights training for a given language pair, you need:
* source and target language corpora (they don't have to be parallel to each other)
* apertium with apertium-transfer modified to use transfer weights (may be checked out from https://svn.code.sf.net/p/apertium/svn/branches/weighted-transfer/)
* language pair of interest with ambiguous rules marked with ids (for an example, see the version of en-es pair from https://svn.code.sf.net/p/apertium/svn/branches/weighted-transfer/)
* kenlm (https://kheafield.com/code/kenlm/)

## Get the corpora
The corpora can be obtained from http://www.statmt.org/wmt12/translation-task.html

## Prepare language model
In order to run the training, you need to make a language model for your target language.

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
Be advised that you might need disk space rougly 15 times the corpus volume for your language model. You can also use gz in order to compress the model file during its creation reducing its size:
```
bin/lmplz -o 5 -T FOLDER_FOR_TMP_FILE <CORPUS_FILE  | gzip >MODEL_NAME.arpa.gz
```
* It is highly recommended that you compile a binary after that as it works significantly faster:
```
bin/build_binary -T FOLDER_FOR_TMP_FILE MODEL_NAME.arpa MODEL_NAME.mmap
```
or, if you used gz in the previous step:
```
bin/build_binary -T FOLDER_FOR_TMP_FILE MODEL_NAME.arpa.gz MODEL_NAME.mmap
'''
Be advised that you might need additional disk space rougly half the arpa file volume for your binary.

## Run training
* Edit configuration file twlconfig.py, which is (hopefully) self-explanatory.
* Run training script:
```
./twlearner.py
```

## Sample run
In order to ensure that everything works fine, you may perform a sample run using prepared corpus:

* Download all parts (years 2007 to 2011) of Spanish news crawl corpora from http://www.statmt.org/wmt12/translation-task.html
* Concatenate them using glue.py script from tools folder.
* Train a language model on the resulting corpus.
* Check out the en-es pair from https://svn.code.sf.net/p/apertium/svn/branches/weighted-transfer/
* Run weights training on new-software-sample.txt file located in the data folder with the en-es pair.

The sample file new-software-sample.txt contains three selected lines with 'new software' and 'this new software' patterns, each of which triggers a pair of ambiguous rules from apertium-en-es.en-es.t1x file, namely ['adj-nom', 'adj-nom-ns'] and ['det-adj-nom', 'det-adj-nom-ns']. Speaking informally, these rules are used to transfer sequences of (adjective, noun) and (determiner, adjective, noun). The first rule in each ambiguous pair specifies that the translations of the adjective and the noun are to be swapped, which is usual for Spanish, hence these rule are specified before their '-ns' counterparts indicating that these are the default rules. The second rule in each ambiguous pair specifies that the translations of the adjective and the noun are not to be swapped, which sometimes happens and depends on lexical units involved.

The contents of the unpruned w1x file should look like the following:
```
<?xml version='1.0' encoding='UTF-8'?>
<transfer-weights>
  <rule-group>
    <rule comment="REGLA: ADJ NOM" id="adj-nom" md5="72e0f329e4cb29910163fa9c9d617ec4">
      <pattern weight="0.2940047506474463">
        <pattern-item lemma="new" tags="adj.sint"/>
        <pattern-item lemma="software" tags="n.sg"/>
      </pattern>
    </rule>
    <rule comment="REGLA: ADJ NOM no-swap-version" id="adj-nom-ns" md5="7df4382f378bae45d951c79e287a31e6">
      <pattern weight="1.7059952493525534">
        <pattern-item lemma="new" tags="adj.sint"/>
        <pattern-item lemma="software" tags="n.sg"/>
      </pattern>
    </rule>
  </rule-group>
  <rule-group>
    <rule comment="REGLA: DET ADJ NOM" id="det-adj-nom" md5="897a67e4ffadec9b7fd515ce0a8d453b">
      <pattern weight="0.262703645221423">
        <pattern-item lemma="its" tags="det.pos.sp"/>
        <pattern-item lemma="own" tags="adj"/>
        <pattern-item lemma="code" tags="n.sg"/>
      </pattern>
      <pattern weight="0.05124922803710481">
        <pattern-item lemma="this" tags="det.dem.sg"/>
        <pattern-item lemma="new" tags="adj.sint"/>
        <pattern-item lemma="software" tags="n.sg"/>
      </pattern>
    </rule>
    <rule comment="REGLA: DET ADJ NOM no-swap-version" id="det-adj-nom-ns" md5="13f1c5ed0615ae8f9d3142aed7a3855f">
      <pattern weight="0.737296354778577">
        <pattern-item lemma="its" tags="det.pos.sp"/>
        <pattern-item lemma="own" tags="adj"/>
        <pattern-item lemma="code" tags="n.sg"/>
      </pattern>
      <pattern weight="0.9487507719628953">
        <pattern-item lemma="this" tags="det.dem.sg"/>
        <pattern-item lemma="new" tags="adj.sint"/>
        <pattern-item lemma="software" tags="n.sg"/>
      </pattern>
    </rule>
  </rule-group>
</transfer-weights>
```

This would mean that '-ns' versions of both rules are preferred for each pattern, which tells the transfer module that the translations of 'new' and 'software' should not be swapped (as specified in '-ns' versions of both rules), since in Spanish the adjective 'nuevo' is usually put before the noun as opposed to the fact that most adjectives are put after the noun.
