# apertium-weights-learner

This is a python3 script that can be used for transfer weights training (see https://wiki.apertium.org/wiki/Ideas_for_Google_Summer_of_Code/Weighted_transfer_rules). For now, it only allows for fully lexicalized patterns to be extracted (i.e., a sequence of tokens with lemmas and full sets of tags).

## Prerequisites
To run this version of transfer weights training for a given language pair, you need:
* source and target language corpora (they don't have to be parallel to each other)
* apertium with apertium-transfer modified to use transfer weights (may be checked out from https://svn.code.sf.net/p/apertium/svn/branches/weighted-transfer/)
* language pair of interest with ambiguous rules marked with ids (for an example, see the version of en-es pair from https://svn.code.sf.net/p/apertium/svn/branches/weighted-transfer/)
* kenlm (https://kheafield.com/code/kenlm/)

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
bin/lmplz -o 5 -T FOLDER_FOR_TMP_FILE <CORPUS_FILE | gzip >MODEL_NAME.arpa.gz
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
* Edit configuration file default.ini, which is (hopefully) self-explanatory, or specify your own config in a separate file.
* Run training script:
** with default config:
```
python3 twlearner.py
```
** with user-defined config in a file config.ini:
```
python3 twlearner.py -c 'config.ini'
```

## Sample run
In order to ensure that everything works fine, you may perform a sample run using prepared corpus:

* Download and unpack all parts (years 2007 to 2011) of Spanish news crawl corpora from http://www.statmt.org/wmt12/translation-task.html
* Concatenate them using glue.py script from 'tools' folder (i.e., assuming you are in apertium-weights-learner folder):
```
tools/glue.py path/to/folder/where/corpus/parts/are glued_corpus
```
* Train a language model on the resulting corpus (i.e., cd into build folder of kenlm model and type):
```
bin/lmplz -o 5 -T folder/for/tmpfile </path/to/glued_corpus | gzip >model.arpa.gz
bin/build_binary -T folder/for/tmpfile model.arpa.gz model.mmap
```
* Check out the en-es pair from https://svn.code.sf.net/p/apertium/svn/branches/weighted-transfer/
* Run weights training on new-software-sample.txt file located in the data folder with the en-es pair, i.e., edit twlconfig.py accordingly and run:
```
./twlearner.py
```

The sample file new-software-sample.txt contains three selected lines with 'new software' and 'this new software' patterns, each of which triggers a pair of ambiguous rules from apertium-en-es.en-es.t1x file, namely ['adj-nom', 'adj-nom-ns'] and ['det-adj-nom', 'det-adj-nom-ns']. Speaking informally, these rules are used to transfer sequences of (adjective, noun) and (determiner, adjective, noun). The first rule in each ambiguous pair specifies that the translations of the adjective and the noun are to be swapped, which is usual for Spanish, hence these rule are specified before their '-ns' counterparts indicating that these are the default rules. The second rule in each ambiguous pair specifies that the translations of the adjective and the noun are not to be swapped, which sometimes happens and depends on lexical units involved.

The contents of the unpruned w1x file without generalizing patterns should look like the following:
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

## Generalizing the patterns
Setting parameter generalize to yes in config file allows the learning script to learn partially generalized patterns as well, i.e. lemmas are partially removed from the pattern in all possible combinations and stored with the same scores as for the full pattern.

## Pruning
You can also prune the obtained weights file with prune.py script from 'tools' folder. Pruning is a process of eliminating redundant weighted patterns, i.e.:
For each rule group:
for each pattern that is present in more than one rule:
* keep only the entry in the rule with the highest weight, and set the weight to 1
* if the rule with the entry with weight = 1 happens to be the default (first) rule, remove that entry from the weights file altogether, since it will be the rule applied anyway.

The idea behind the pruning process is that in fact, we only want to weight exceptions from the default rule. Pruned weights file doesn't offer any significant speed advantages with the current realization but it still reduces memory footprint at translation time and this allows to learn weights from bigger corpora.

## Removing generalized patterns
If you just killed 5 hours of your machine time to obtain a weights file with generalized patterns and then suddenly realized that you want a file without them as well, you can use remgen.py from 'tools' folder to achieve exactly that. 

## Testing
Once the weights are obtained, their impact can be tested on a parallel corpus using the 'weights-test.sh' script from the 'testing' folder, which contains a simple config akin to the weights learning script. If you want to test your weights specifically on the lines containing ambiguous chunks, you can first run your test corpora through condense.py script from 'tools' folder.
