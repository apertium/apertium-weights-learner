#! /bin/sh

PAIR_FOLDER="../../apertium-en-es"
PAIR_PREFIX=$PAIR_FOLDER/apertium-en-es.en-es
WEIGHTS_FILE=$PAIR_FOLDER/2007-en-30000-rule-weights-prunned.w1x
PAIR_NAME="en-es"
SOURCE_CORPUS="nc-v7-100000.es-en.en"
REFERENCE_CORPUS="nc-v7-100000.es-en.es"
UNWEIGHTED_OUTPUT="nc-v7-100000.es-en.en.es.unweighted"
WEIGHTED_OUTPUT="nc-v7-100000.es-en.en.es.weighted"
SCRIPTS_FOLDER="SCRIPTS"

echo "Translating unweighted"

time apertium -d $PAIR_FOLDER/ $PAIR_NAME-tagger $SOURCE_CORPUS | apertium-pretransfer | lt-proc -b $PAIR_FOLDER/$PAIR_NAME.autobil.bin | apertium-transfer -b $PAIR_PREFIX.t1x $PAIR_FOLDER/$PAIR_NAME.t1x.bin 2>unweighted.log | apertium-interchunk $PAIR_PREFIX.t2x $PAIR_FOLDER/$PAIR_NAME.t2x.bin | apertium-postchunk $PAIR_PREFIX.t3x $PAIR_FOLDER/$PAIR_NAME.t3x.bin | lt-proc -g $PAIR_FOLDER/$PAIR_NAME.autogen.bin | apertium-retxt | sed 's/[*#@~]//g' > $UNWEIGHTED_OUTPUT

echo "\nTranslating weighted"

time apertium -d $PAIR_FOLDER/ $PAIR_NAME-tagger $SOURCE_CORPUS | apertium-pretransfer | lt-proc -b $PAIR_FOLDER/$PAIR_NAME.autobil.bin | apertium-transfer -bw $WEIGHTS_FILE $PAIR_PREFIX.t1x $PAIR_FOLDER/$PAIR_NAME.t1x.bin 2>weighted.log | apertium-interchunk $PAIR_PREFIX.t2x $PAIR_FOLDER/$PAIR_NAME.t2x.bin | apertium-postchunk $PAIR_PREFIX.t3x $PAIR_FOLDER/$PAIR_NAME.t3x.bin | lt-proc -g $PAIR_FOLDER/$PAIR_NAME.autogen.bin | apertium-retxt | sed 's/[*#@~]//g' > $WEIGHTED_OUTPUT

python3 bleu_test.py $REFERENCE_CORPUS $UNWEIGHTED_OUTPUT $WEIGHTED_OUTPUT
