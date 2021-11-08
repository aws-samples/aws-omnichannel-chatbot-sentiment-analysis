import json
import csv
import random

madeUpText = {}
outputLists = []

def createRandomExample(entityText, entityType):
    selections = madeUpText[entityType]
    entry = random.randrange(0, len(madeUpText[entityType])-1, 1)
    chosenString = selections[entry]
    return chosenString.replace('{KEY}', entityText)

def writeOutTrainingDocument():
    with open('./entity-training-docs.csv', 'w') as documentFile:
        for trainingLine in outputLists:
            documentFile.write(trainingLine[0])
            documentFile.write('\n')

def writeOutAnnotationDocument():
    with open('./entity-training-annotation.csv', 'w') as annotationFile:
        fieldnames = ['File', 'Line', 'Begin Offset', 'End Offset', 'Type']
        annotationWriter = csv.DictWriter(annotationFile, fieldnames=fieldnames)
        annotationWriter.writeheader()
        lineNum = 0
        for trainingLine in outputLists:
            annotationWriter.writerow({
                'File': 'entity-training-docs.csv',
                'Line': lineNum,
                'Begin Offset': trainingLine[1],
                'End Offset': trainingLine[2],
                'Type': trainingLine[4]
            })
            lineNum += 1

# Seed the random number generator
random.seed()

# Read in the JSON
with open('./entity-sentences.json') as f:
    data = json.load(f)

# Loop around each of the entities
for key in data['Entities']:
    print(key['Key'])
    keyList = []
    for sentence in key['Sentences']:
        keyList.append(sentence)
    madeUpText[key['Key']] = keyList

with open('entity-list.csv', newline='') as csvfile:
    entityReader = csv.reader(csvfile)
    line = 0
    for row in entityReader:
        line += 1
        if line > 1:
            # Pick out a random training line for this entry
            entityText = row[0]
            entityType = row[1]
            randomLine = createRandomExample(entityText, entityType)

            # Find the annotated location and add it to our list
            startPos = randomLine.find(entityText)
            endPos = startPos + len(entityText)
            outputLists.append([randomLine, startPos, endPos, entityText, entityType])

# Now write out our two documents
writeOutTrainingDocument()
writeOutAnnotationDocument()