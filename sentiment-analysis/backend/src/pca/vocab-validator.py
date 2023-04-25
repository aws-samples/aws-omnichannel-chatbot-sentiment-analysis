import csv
import re
import sys

# Supported Languages
SUPPORTED_LANGS = ["en", "tr"]

newIPAList = []

# Check the parameters
numArgs = len(sys.argv)
if (numArgs < 2) or (numArgs > 3):
    print("Usage: vocab-validation csvFilename {language}")

# Extract the filename and language code (default to en)
filename = sys.argv[1]
if numArgs == 3:
    langCode = sys.argv[2].lower()
    if langCode not in SUPPORTED_LANGS:
        print("Usage: vocab-validation csvFilename {language}")
        print("-- {0} is not in the supported language list: {1}".format(langCode, SUPPORTED_LANGS))
else:
    langCode = "en"

# Pick out correct codes
if langCode == "en":
    # English values
    VALID_COMB = [{"Split": "a ʊ", "Combo": "aʊ"},
                  {"Split": "a ɪ", "Combo": "aɪ"},
                  {"Split": "e ɪ", "Combo": "eɪ"},
                  {"Split": "ɔ ɪ", "Combo": "ɔɪ"},
                  {"Split": "o ʊ", "Combo": "oʊ"},
                  {"Split": "n ̩", "Combo": "n̩"},
                  {"Split": "l ̩", "Combo": "l̩"}]

    VALID_PAIR = ["aʊ", "aɪ", "eɪ", "ɔɪ", "oʊ", "n̩", "l̩"]

    VALID_CHAR = ["w", "ɪ", "z", "b", "æ", "d", "ð", "ŋ", "f", "ɑ", "g", "ɔ", "h", "i", "ə",
                  "j", "ɛ", "k", "ɝ", "l", "ɡ", "m", "ɹ", "n", "ʃ", "ʊ", "ʌ", "p", "ʍ", "s",
                  "ʒ", "t", "ʤ", "u", "ʧ", "v", "θ"]

    VALID_PHRASE = "^[a-zA-Z.'-]+$"
    VALID_SOUNDS = "^[a-zA-Z.'-]+"
elif langCode == "tr":
    VALID_COMB = [{"Split": "a ː", "Combo": "aː"},
                  {"Split": "e ː", "Combo": "eː"},
                  {"Split": "i ː", "Combo": "iː"},
                  {"Split": "o ː", "Combo": "oː"},
                  {"Split": "u ː", "Combo": "uː"},
                  {"Split": "y ː", "Combo": "yː"},
                  {"Split": "ø ː", "Combo": "øː"},
                  {"Split": "ɯ ː", "Combo": "ɯː"}]

    VALID_PAIR = ["aː", "eː", "iː", "oː", "uː", "yː", "øː", "ɯː"]

    VALID_CHAR = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o",
                  "p", "s", "t", "u", "v", "w", "y", "z", "ø", "ŋ", "ɟ", "ɣ", "ɫ", "ɯ", "ɾ",
                  "ʃ", "ʒ", "ʔ", "ʤ", "ʧ"]

    VALID_PHRASE = "^[a-zA-Z.'-ÇÖÜâäçèéêíîóöûüĞğİıŞşšž]+$"
    VALID_SOUNDS = "^[a-zA-Z.'-ÇÖÜâäçèéêíîóöûüĞğİıŞşšž]+"

with open(filename, newline='') as csvfile:
    vocab = csv.reader(csvfile)
    line = 0
    for row in vocab:
        line += 1
        if line > 1:
            # Pick out a random training line for this entry
            phrase = row[0]
            displayAS = row[1]
            soundsLike = row[2]
            ipaNewText = row[3]

            # Ensure that the Phrase is only [A-Z], [a-z] and [.-']
            if not re.search(VALID_PHRASE, phrase) or phrase.endswith("-"):
                print("Failed: phrase [" + phrase + "] violates allowed characters")
                line = -1

            # Ensure that SoundsLike is also only [A-Z], [a-z] and [.-']
            if " " in soundsLike:
                print("Failed: soundsLike [" + soundsLike + "] contains SPACE characters")
                line = -1
            if (soundsLike != "") and not re.search(VALID_SOUNDS, soundsLike):
                print("Failed: soundsLike [" + soundsLike + "] violates allowed characters")
                line = -1

            # Do some substitutions / replacements in the IPA string (from standard IPA forms)
            if " " in ipaNewText:
                print("Failed: IPA phrase [" + ipaNewText + "] contains SPACE characters")

            # Only worry about the IPA if there is something there
            if ipaNewText != "":
                # Now format the IPA phrase for the correct character separation
                ipaNewText = " ".join(ipaNewText)
                for combo in VALID_COMB:
                    if combo["Split"] in ipaNewText:
                        ipaNewText = ipaNewText.replace(combo["Split"], combo["Combo"])

                # Ensure no disallowed characters exist in the IPA
                ipaNewText = ipaNewText.split(' ')
                for token in ipaNewText:
                    if token not in VALID_CHAR:
                        if token not in VALID_PAIR:
                            print("Failed: found [" + token + "] in " + phrase)
                            line = -1

            if line == -1:
                break

            # Print success and store set, generating new
            finalIPA = " ".join(ipaNewText)

            print("Phrase: " + phrase + " : " + finalIPA + soundsLike)
            newIPAList.append({'Phrase': phrase, 'DisplayAs': displayAS, 'SoundsLike': soundsLike, 'IPA': finalIPA})

with open(filename+'.txt', 'w', newline='') as file:
    fieldnames = ['Phrase', 'DisplayAs', 'IPA', 'SoundsLike']
    file.write('\t'.join(fieldnames) + '\n')
    for entry in newIPAList:
        file.write(entry['Phrase'] + '\t' + entry['DisplayAs'] + '\t' + entry['IPA'] + '\t' + entry["SoundsLike"] + '\n')
