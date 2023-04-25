"""
Parses the output from an Amazon Transcribe job into turn-by-turn
speech segments with sentiment analysis scores from Amazon Comprehend
"""

from pathlib import Path
from datetime import datetime
import pcaconfiguration as cf
import time
import re
import sys
import json
import boto3
import gzip

# Sentiment helpers
MIN_SENTIMENT_LENGTH = 16

# PII and other Markers
PII_PLACEHOLDER = "[PII]"
TMP_DIR = "/tmp"

# Overridden access keys - only used by CLI-style clients
overrides = sys.modules[__name__]
overrideAccessKeyID = ""
overrideSecretAccessKey = ""


def setAWSAccessKeys(accessKeyID, secretAccessKey):
    """
    Allows external client to specify keys, otherwise we use what we inherit,
    and don't forget to pass them to our configuration module
    """
    overrides.overrideAccessKeyID = accessKeyID
    overrides.overrideSecretAccessKey = secretAccessKey
    cf.setAWSAccessKeys(accessKeyID, secretAccessKey)


class SpeechSegment:
    """ Class to hold information about a single speech segment """
    def __init__(self):
        self.segmentStartTime = 0.0
        self.segmentEndTime = 0.0
        self.segmentSpeaker = ""
        self.segmentText = ""
        self.segmentConfidence = []
        self.segmentSentimentScore = -1.0    # -1.0 => no sentiment calcualated
        self.segmentPositive = 0.0
        self.segmentNegative = 0.0
        self.segmentIsPositive = False
        self.segmentIsNegative = False
        self.segmentAllSentiments = []
        self.segmentCustomEntities = []
        self.jsonOutputFilename = ""


class TranscribeParser:

    def __init__(self, minSentimentPos: float, minSentimentNeg: float, comprehendEntityModel: str):
        self.min_sentiment_positive: float  = minSentimentPos
        self.min_sentiment_negative: float = minSentimentNeg
        self.transcribeJobInfo: str = ""
        self.conversationLanguageCode = ""
        self.conversationTime = ""
        self.speechSegmentList = []
        self.headerEntityDict = {}
        self.numWordsParsed = 0
        self.cummulativeWordAccuracy = 0.0
        self.accessKeyID = overrideAccessKeyID
        self.secretAccessKey = overrideSecretAccessKey
        self.comprehendEntityModel = comprehendEntityModel
        self.maxSpeakerIndex = 0
        cf.loadConfiguration()

    def getBoto3Client(self, serviceName):
        """
        Gets a basic Boto3 client for the given service name, using the right credentials
        """
        if self.accessKeyID == "":
            client = boto3.client(serviceName)
        else:
            client = boto3.client(serviceName,
                                  aws_access_key_id = self.accessKeyID,
                                  aws_secret_access_key = self.secretAccessKey)

        return client

    def getBoto3Resource(self, serviceName):
        """
        Gets a basic Boto3 resource for the given service name, using the right credentials
        """
        if self.accessKeyID == "":
            client = boto3.resource(serviceName)
        else:
            client = boto3.resource(serviceName,
                                    aws_access_key_id = self.accessKeyID,
                                    aws_secret_access_key = self.secretAccessKey)

        return client

    def generateSpeakerSentimentTrend(self, speaker, spkNum):
        '''
        Generates and returns a sentiment trend block for this speaker

        {
          "Speaker": "string",
          "AverageSentiment": "float",
          "SentimentChange": "float"
        }
        '''
        speakerTrend = {}
        speakerTrend["Speaker"] = speaker

        speakerTurns = 0
        sumSentiment = 0.0
        firstSentiment = 0.0
        finalSentiment = 0.0
        for segment in self.speechSegmentList:
            if segment.segmentSpeaker == speaker:
                # Increment our counter for number of speaker turns and update the last turn score
                speakerTurns += 1

                if segment.segmentIsPositive or segment.segmentIsNegative:
                    # Only really interested in Positive/Negative turns for the stats.  We need to
                    # average out the calls between +/- 1, so we sum each turn as follows:
                    # ([sentiment] - [sentimentBase]) / (1 - [sentimentBase])
                    # with the answer positive/negative based on the sentiment.  We rebase as we have
                    # thresholds to declare turns as pos/neg, so might be in the range 0.30-1.00. but
                    # Need this changed to 0.00-1.00
                    if segment.segmentIsPositive:
                        sentimentBase = self.min_sentiment_positive
                        signModifier = 1.0
                    else:
                        sentimentBase = self.min_sentiment_negative
                        signModifier = -1.0

                    # Calculate score and add it to our total
                    turnScore = signModifier * ((segment.segmentSentimentScore - sentimentBase) / (1.0 - sentimentBase))
                    sumSentiment += turnScore

                    # Assist to first-turn score if this is us, and update the last-turn
                    # score, as we dont' know if this is the last turn for this speaker
                    if speakerTurns == 1:
                        firstSentiment = turnScore
                    finalSentiment = turnScore
                else:
                    finalSentiment = 0.0

        # Log our trends for this speaker
        speakerTrend["SentimentChange"] = finalSentiment - firstSentiment
        speakerTrend["AverageSentiment"] = sumSentiment / speakerTurns

        return speakerTrend

    def createOutputConversationAnalytics(self):
        '''
          "ConversationAnalytics": {
            "ConversationTime": "string"
            "ProcessTime": "string",
            "LanguageCode": "string",
            "EntityRecognizerName": "string",
            "SpeakerLabels": [
              {
                "Speaker": "string",
                "DisplayText": "string"
              }
            ],
            "SentimentTrends": [
              {
                "Speaker": "string",
                "AverageSentiment": "float",
                "SentimentChange": "float"
              }
            ],
            "CustomEntities": [
              {
                  "Name": "string",
                  "Count": "integer",
                  "Values": [ "string" ]
              }
            ],
            "SourceInformation": [
              {
                "TranscribeJobInfo": {
                  "TranscriptionJobName": "string",
                  "CompletionTime": "string",
                  "VocabularyName": "string",
                  "MediaFormat": "string",
                  "MediaSampleRateHertz": "integer",
                  "MediaFileUri": "string",
                  "ChannelIdentification": "boolean",
                  "AverageAccuracy": "float"
                }
              }
            ]
          }
        '''
        resultsHeaderInfo = {}

        # Basic information.  Note, we expect the input stream processing mechanism
        # to set the conversation time - if it is not set then we have no choice
        # but to default this to the current processing time.
        resultsHeaderInfo["ConversationTime"] = self.conversationTime
        resultsHeaderInfo["ProcessTime"] = str(datetime.now())
        resultsHeaderInfo["LanguageCode"] = self.conversationLanguageCode
        if self.conversationTime == "":
            resultsHeaderInfo["ConversationTime"] = resultsHeaderInfo["ProcessTime"]

        # Only add a reference to the custom Comprehend models if they exist
        if self.comprehendEntityModel != "":
            resultsHeaderInfo["EntityRecognizerName"] = self.comprehendEntityModel

        # Build up a list of speaker labels from the config; note that if we
        # have more speakers than configured then we still return something
        speakerLabels = []
        for speaker in range(self.maxSpeakerIndex + 1):
            nextLabel = {}
            nextLabel["Speaker"] = "spk_" + str(speaker)
            try:
                nextLabel["DisplayText"] = cf.appConfig[cf.CONF_SPKRPREFIX + str(speaker)]
            except:
                nextLabel["DisplayText"] = "Unknown-" + str(speaker)
            speakerLabels.append(nextLabel)
        resultsHeaderInfo["SpeakerLabels"] = speakerLabels

        # Sentiment Trends
        sentimentTrends = []
        for speaker in range(self.maxSpeakerIndex + 1):
            sentimentTrends.append(self.generateSpeakerSentimentTrend("spk_" + str(speaker), speaker))
        resultsHeaderInfo["SentimentTrends"] = sentimentTrends

p
        # Decide which source information block to add - only one for now
        transcribeSourceInfo = {}
        transcribeSourceInfo["TranscribeJobInfo"] = self.createOutputTranscribeJobInfo()
        sourceInfo = []        # Detected custom entity summaries next
        customEntityList = []
        for entity in self.headerEntityDict:
            nextEntity = {}
            nextEntity['Name'] = entity
            nextEntity['Count'] = len(self.headerEntityDict[entity])
            nextEntity['Values'] = self.headerEntityDict[entity]
            customEntityList.append(nextEntity)
        resultsHeaderInfo["CustomEntities"] = customEntityList

        sourceInfo.append(transcribeSourceInfo)
        resultsHeaderInfo["SourceInformation"] = sourceInfo

        return resultsHeaderInfo

    def createOutputTranscribeJobInfo(self):
        '''
        "TranscribeJobInfo": {
            "TranscriptionJobName": "string",
            "CompletionTime": "string",
            "VocabularyName": "string",
            "MediaFormat": "string",
            "MediaSampleRateHertz": "integer",
            "MediaFileUri": "string",
            "ChannelIdentifcation": "boolean",
            "AverageAccuracy": "float"
         }
        '''
        transcribeJobInfo = {}

        # Some fields we pick off the basic job info
        transcribeJobInfo["TranscriptionJobName"] = self.transcribeJobInfo["TranscriptionJobName"]
        transcribeJobInfo["CompletionTime"] = str(self.transcribeJobInfo["CompletionTime"])
        transcribeJobInfo["MediaFormat"] = self.transcribeJobInfo["MediaFormat"]
        transcribeJobInfo["MediaSampleRateHertz"] = self.transcribeJobInfo["MediaSampleRateHertz"]
        transcribeJobInfo["MediaFileUri"] = self.transcribeJobInfo["Media"]["MediaFileUri"]
        transcribeJobInfo["ChannelIdentification"] = int(self.transcribeJobInfo["Settings"]["ChannelIdentification"])
        transcribeJobInfo["AverageAccuracy"] = self.cummulativeWordAccuracy / float(self.numWordsParsed)

        # Vocabulary name is optional
        if "VocabularyName" in self.transcribeJobInfo["Settings"]:
            transcribeJobInfo["VocabularyName"] = self.transcribeJobInfo["Settings"]["VocabularyName"]

        return transcribeJobInfo

    def createOutputSpeechSegments(self):
        '''
        Creates a list of speech segments for this conversation, including custom entities

         "SpeechSegments": [
            {
              "SegmentStartTime": "float",
              "SegmentEndTime": "float",
              "SegmentSpeaker": "string",
              "OriginalText": "string",
              "DisplayText": "string",
              "TextEdited": "boolean",
              "SentimentIsPositive": "boolean",
              "SentimentIsNegative": "boolean",
              "SentimentScore": "float",
              "BaseSentimentScores": {
                "Positive": "float",
                "Negative": "float",
                "Neutral": "float",
                "Mixed": "float"
              },
              "EntitiesDetected": [
                {
                  "Type": "string",
                  "Text": "string",
                  "BeginOffset": "integer",
                  "EndOffset": "integer",
                  "Score": "float"
                }
              ],
              "WordConfidence": [
                {
                  "Text": "string",
                  "Confidence": "float",
                  "StartTime": "float",
                  "EndTime": "float"
                }
              ]
            }
          ]
          '''
        speechSegments = []

        # Loop through each of our speech segments
        # for segment in self.speechSegmentList:
        for segment in self.speechSegmentList:
            nextSegment = {}

            # Pick everything off our structures
            nextSegment["SegmentStartTime"] = segment.segmentStartTime
            nextSegment["SegmentEndTime"] = segment.segmentEndTime
            nextSegment["SegmentSpeaker"] = segment.segmentSpeaker
            nextSegment["OriginalText"] = segment.segmentText
            nextSegment["DisplayText"] = segment.segmentText
            nextSegment["TextEdited"] = 0
            nextSegment["SentimentIsPositive"] = int(segment.segmentIsPositive)
            nextSegment["SentimentIsNegative"] = int(segment.segmentIsNegative)
            nextSegment["SentimentScore"] = segment.segmentSentimentScore
            nextSegment["BaseSentimentScores"] = segment.segmentAllSentiments
            nextSegment["EntitiesDetected"] = segment.segmentCustomEntities
            nextSegment["WordConfidence"] = segment.segmentConfidence

            # Add what we have to the full list
            speechSegments.append(nextSegment)

        return speechSegments

    def outputAsJSON(self):
        '''
        {
            "ConversationAnalytics": { },
            "SpeechSegments": [ ]
        }
        '''
        outputJson = {}
        outputJson["ConversationAnalytics"] = self.createOutputConversationAnalytics()
        outputJson["SpeechSegments"] = self.createOutputSpeechSegments()

        return outputJson

    def getTranscribeJobInfo(self):
        return self.transcribeJobInfo

    def getSpeechSegmentList(self):
        return self.speechSegmentList

    def getJSONOutputFilename(self):
        """
        Simply returns the JSON filename for the associated Transcribe job name
        """
        return self.jsonOutputFilename

    def mergeSpeakerSegments(self, inputSegmentList):
        """
        Merges together two adjacent speaker segments if (a) the speaker is
        the same, and (b) if the gap between them is less than 3 seconds
        """
        outputSegmentList = []
        lastSpeaker = ""
        lastSegment = None

        # Step through each of our defined speaker segments
        for segment in inputSegmentList:
            if (segment.segmentSpeaker != lastSpeaker) or ((segment.segmentStartTime - lastSegment.segmentEndTime) >= 3.0):
                # Simple case - speaker change or > 3.0 second gap means new output segment
                outputSegmentList.append(segment)

                # This is now our base segment moving forward
                lastSpeaker = segment.segmentSpeaker
                lastSegment = segment
            else:
                # Same speaker, short time, need to copy this info to the last one
                lastSegment.segmentEndTime = segment.segmentEndTime
                lastSegment.segmentText += " " + segment.segmentText
                segment.segmentConfidence[0]["Text"] = " " + segment.segmentConfidence[0]["Text"]
                for wordConfidence in segment.segmentConfidence:
                    lastSegment.segmentConfidence.append(wordConfidence)

        return outputSegmentList

    def debugMapComprehendEntityJob(self, filename):
        if filename ==   "redacted-0a.93.a0.3e.00.00-09.26.37.755-09-23-2019.wav.json.plaintxt":
            return "0238a652d115f32ca2d0cc946d3e8760"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.11.32.483-09-10-2019.wav.json.plaintxt":
            return "e404960bdc7d180b200c895579926551"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.28.29.553-09-17-2019.wav.json.plaintxt":
            return "0984260996421b7ce9380bfab7c8bad5"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.28.52.023-09-10-2019.wav.json.plaintxt":
            return "010641e9ae0b7c18d4411c710aa2be71"
        elif filename == "redacted-0a.93.a0.3f.00.00-10.41.54.226-09-20-2019.wav.json.plaintxt":
            return "9fd46690e172f784b01c2b67c940a760"
        elif filename == "redacted-0a.93.a0.3f.00.00-10.46.53.432-09-19-2019.wav.json.plaintxt":
            return "587591f84b188e9827b751569ecf8cf7"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.31.33.923-09-16-2019.wav.json.plaintxt":
            return "8ae9621ba65103295308c2955fad4fc1"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.30.26.530-09-05-2019.wav.json.plaintxt":
            return "fce2dfd35300ca5eba7caaa362f93ee1"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.25.51.067-09-26-2019.wav.json.plaintxt":
            return "2741baeb0f2d5cde938cf8cd393e4a36"
        elif filename == "redacted-0a.93.a0.3e.00.00-09.13.43.164-09-16-2019.wav.json.plaintxt":
            return "7a90feecbe87f179e5732fe7856aacb9"
        else:
            assert False, "Couldn't find Comprehend Entity job for requested file"

    def detectCustomEntities(self, outputFilename):
        """
        Detects custom entities in the segments.  It's an asynchronous call to Comprehend, so makes sense to pull
        out all of the text lines into one file, which needs to be sent to S3, and do them all at once.  This function
        will then wait for completion, and insert what it finds into the relevant place in the speech segments
        """
        # If we have no model base then get out quick
        if self.customEntityEndpointName == "":
            # Not defined
            return

        # Need to get the language-specific version of the model, using the Sentiment supported languages
        client = self.getBoto3Client("comprehend")
        if self.conversationLanguageCode == "":
            # No language defined - use the base model as-is
            modelName = self.customEntityEndpointName
        else:
            modelName = self.customEntityEndpointName + "-" + self.setComprehendLanguageCode(client, "")

        # Get the ARN for our classifier, getting out quickly if there
        # isn't one defined or if we can't find the one that is defined
        recognizerList = client.list_entity_recognizers()
        recognizer = list(filter(lambda x: x["EntityRecognizerArn"].endswith(modelName),
                                     recognizerList["EntityRecognizerPropertiesList"]))
        if recognizer == []:
            # Doesn't exist
            return
        recognizerArn = recognizer[0]["EntityRecognizerArn"]

        # Create a temp file containing every turn that we have
        tempTextFilename = TMP_DIR + '/' + outputFilename
        comprehendInputFile = open(tempTextFilename, "w")
        for turn in self.speechSegmentList:
            comprehendInputFile.write(turn.segmentText)
            comprehendInputFile.write("\n")
        comprehendInputFile.close()

        # Now upload to S3 so that Comprehend can use it
        s3Resource = self.getBoto3Resource('s3')
        s3OutputBucket = cf.appConfig[cf.CONF_S3BUCKET_OUTPUT]
        s3OutputKey = cf.appConfig[cf.CONF_COMPKEY]
        s3Resource.meta.client.upload_file(Filename = tempTextFilename,
                                           Bucket = s3OutputBucket,
                                           Key = s3OutputKey + '/' + outputFilename)

        # Start a Comprehend Custom Entity Detection job
        comprehendClient = self.getBoto3Client("comprehend")
        s3FileUri = "s3://" + s3OutputBucket + '/' + s3OutputKey + '/' + outputFilename
        s3ResultsUri = "s3://" + s3OutputBucket + '/' + s3OutputKey + '/results'
        response = {'JobId': self.debugMapComprehendEntityJob(outputFilename), 'JobStatus': 'SUBMITTED'}
        # response = comprehendClient.start_entities_detection_job(
        #     InputDataConfig = {
        #         'S3Uri': s3FileUri,
        #         'InputFormat': 'ONE_DOC_PER_LINE'
        #     },
        #     OutputDataConfig = {
        #         'S3Uri': s3ResultsUri
        #     },
        #     DataAccessRoleArn = cf.appConfig[cf.CONF_COMPIAMROLE],
        #     LanguageCode = "en",
        #     EntityRecognizerArn = recognizerArn
        # )

        # Wait for it to complete, which will be several minutes (Step Functions backons...)
        jobId = response['JobId']
        status = response
        while (status['JobStatus'] == "SUBMITTED") or (status['JobStatus'] == 'IN_PROGRESS'):
            status = comprehendClient.describe_entities_detection_job(JobId = jobId)['EntitiesDetectionJobProperties']
            # time.sleep(30)

        # Only continue if we actually completed properly
        if status['JobStatus'] == 'COMPLETED':
            # Download and unpack the results file
            resultsFileURI = status['OutputDataConfig']['S3Uri']
            offsetFilepath = resultsFileURI.find(s3OutputBucket) + len(s3OutputBucket) + 1
            outputFilename = resultsFileURI[offsetFilepath:]

            # Just want the finale filename part for the local temp file
            revFilename = outputFilename[len(outputFilename)::-1]
            reverseOffset = revFilename.find("/")
            localFilename = TMP_DIR + '/' + revFilename[:reverseOffset][len(revFilename[:reverseOffset])::-1]

            # Download the results
            s3Client = self.getBoto3Client('s3')
            s3Client.download_file(s3OutputBucket, outputFilename, localFilename)

            with gzip.open(localFilename, 'rb') as f:
                for line in f:
                    try:
                        # Get the line from the file, and strip the leading pre-JSON characters
                        lineInFile = str(line)
                        entityResult = lineInFile[lineInFile.find('{'):]

                        # Now take out the trailing non-JSON entities
                        revJSONData = entityResult[len(entityResult)::-1]
                        reverseOffset = revJSONData.find('}')
                        jsonDataLine = revJSONData[reverseOffset:][len(revJSONData[reverseOffset:])::-1]
                        parsedHeader = json.loads(jsonDataLine)
                        lineNum = int(parsedHeader['Line'])

                        # Step through and parse each line of JSON
                        for entity in parsedHeader['Entities']:
                            self.extractEntitiesFromLine(entity, self.speechSegmentList[lineNum], ["BRAND", "INGREDIENT"])
                    except:
                        # If the line wasn't JSON then it will fail (e.g. the filename entry line)
                        pass

            # Now we need to remove duplicates from the header counts and just replace with a count
            for entityType in self.headerEntityDict:
                originalList = self.headerEntityDict[entityType]
                reducedList = list(dict.fromkeys(originalList))
                self.headerEntityDict[entityType] = reducedList

    def extractEntitiesFromLine(self, entityLine, speechSegment, typeFilter):
        """
        Takes a speech segment and an entity line from Comprehend - standard or custom models - and
        if the entity type is in our input type filter (or is blank) then add it to the transcript
        """
        if float(entityLine['Score']) >= cf.appConfig[cf.CONF_ENTITYCONF]:
            entityType = entityLine['Type']

            # If we have a type filter then ensure we match it before adding the entry
            if (typeFilter == []) or (entityType in typeFilter):

                # Ensure we have an entry in our collection for this key
                if entityType not in self.headerEntityDict:
                    self.headerEntityDict[entityType] = []

                keyDetails = self.headerEntityDict[entityType]
                keyDetails.append(entityLine['Text'])
                self.headerEntityDict[entityType] = keyDetails

                # Now do the same with the SpeechSegment, but append the full details
                speechSegment.segmentCustomEntities.append(entityLine)

    def createComprehendLanguageCode(self, boto3Client, sampleText):
        '''
        Based upon the language defined by the input stream, or by the dominant language detected by Comprehend
        if one hasn't been defined, return the best-match language code for Comprehend to use on this example.
        It is "best-match" as Comprehend can model in EN, but has no differentiation between EN-US and EN-GB.
        If we cannot determine a language to use then we return an empty string

        @return language code usable by Comprehend
        '''
        targetLangModel = ""
        baseLangCode = self.conversationLanguageCode

        try:
            if baseLangCode == "":
                # No language defined - need to get dominant language of sample text via Comprehend
                dominantLang = boto3Client.detect_dominant_language(Text = sampleText)
                baseLangCode = dominantLang["Languages"][0]["LanguageCode"]

            for checkLangCode in cf.appConfig[cf.CONF_COMP_LANGS]:
                if baseLangCode.startswith(checkLangCode):
                    targetLangModel = checkLangCode
                    break
        except:
            # If anything fails - e.g. no language detected, no test string, etc, then we have no language
            pass

        return targetLangModel

    def getComprehendSentimentAndLocation(self, segmentList):
        """
        Generates sentiment per speech segment, inserting the results into the input list.
        If we had no valid language for Comprehend to use then we use Neutral for everything
        """
        client = self.getBoto3Client("comprehend")

        # Work out with Comprehend language model to use
        comprehendLangCode = self.setComprehendLanguageCode(client, segmentList[0].segmentText)
        if comprehendLangCode == "":
            # If there's no language model then everything is Neutral
            neutralSentimentSet = {'Positive': 0.0, 'Negative': 0.0, 'Neutral': 1.0, 'Mixed': 0.0}

        # Go through each of our segments
        for nextSegment in segmentList:
            if len(nextSegment.segmentText) >= MIN_SENTIMENT_LENGTH:
                nextText = nextSegment.segmentText
                # If we have a language model then extract sentiment via Comprehente
                if comprehendLangCode != "":
                    # Get sentiment and standard entity detection from Comprehend
                    sentimentResponse = client.detect_sentiment(Text = nextText, LanguageCode = comprehendLangCode)
                    entityResponse = client.detect_entities(Text = nextText, LanguageCode = comprehendLangCode)

                    # We're only interested in LOCATION entities, but let's get any added on
                    for detectedEntity in entityResponse["Entities"]:
                        self.extractEntitiesFromLine(detectedEntity, nextSegment, ["LOCATION"])

                    # Now onto the sentiment - begin by storing the raw values
                    positiveBase = sentimentResponse["SentimentScore"]["Positive"]
                    negativeBase = sentimentResponse["SentimentScore"]["Negative"]

                    # If we're over the NEGATIVE threshold then we're negative
                    if negativeBase >= self.min_sentiment_negative:
                        nextSegment.segmentSentiment = "Negative"
                        nextSegment.segmentIsNegative = True
                        nextSegment.segmentSentimentScore = negativeBase
                    # Else if we're over the POSITIVE threshold then we're positive,
                    # otherwise we're either MIXED or NEUTRAL and we don't really care
                    elif positiveBase >= self.min_sentiment_positive:
                        nextSegment.segmentSentiment = "Positive"
                        nextSegment.segmentIsPositive = True
                        nextSegment.segmentSentimentScore = positiveBase

                    # Store all of the original sentiments for future use
                    nextSegment.segmentAllSentiments = sentimentResponse["SentimentScore"]
                    nextSegment.segmentPositive = positiveBase
                    nextSegment.segmentNegative = negativeBase
                else:
                    # We had no language - default sentiment, no new entities
                    nextSegment.segmentAllSentiments = neutralSentimentSet
                    nextSegment.segmentPositive = 0.0
                    nextSegment.segmentNegative = 0.0


    def generateSpeakerLabel(self, transcribeSpeaker):
        '''
        Takes the Transcribed-generated speaker, which could be spk_{N} or ch_{N}, and returns the label spk_{N}.
        This allows us to have a consistent label in the output JSON, which means that a header field in the
        output is able to dynamically swap the display labels.  This is needed as we cannot guarantee, especially
        with speaker-separated, who speaks first
        '''
        index = transcribeSpeaker.find("_")
        speaker = int(transcribeSpeaker[index + 1:])
        if speaker > self.maxSpeakerIndex:
            self.maxSpeakerIndex = speaker
        newLabel = "spk_" + str(speaker)
        return newLabel


    def createTurnByTurnSegments(self, transcribeJobFilename):
        """
        Creates a list of conversational turns, splitting up by speaker or if there's a noticeable pause in
        conversation.  Notes, this works differently for speaker-separated and channel-separated files. For speaker-
        the lines are already separated by speaker, so we only worry about splitting up speaker pauses of more than 3
        seconds, but for channel- we have to hunt gaps of 100ms across an entire channel, then sort segments from both
        channels, then merge any together to ensure we keep to the 3-second pause; this way means that channel- files
        are able to show interleaved speech where speakers are talking over one another.  Once all of this is done
        we inject sentiment into each segment.
        """
        speechSegmentList = []

        # Load in the JSON file for processing
        json_filepath = Path(transcribeJobFilename)
        data = json.load(open(json_filepath.absolute(), "r", encoding="utf-8"))

        # Decide on our operational mode and set the overall job language
        isChannelMode = self.transcribeJobInfo["Settings"]["ChannelIdentification"]
        isSpeakerMode = not self.transcribeJobInfo["Settings"]["ChannelIdentification"]
        self.conversationLanguageCode = self.transcribeJobInfo["LanguageCode"]

        lastSpeaker = ""
        lastEndTime = 0.0
        skipLeadingSpace = False
        confidenceList = []
        nextSpeechSegment = None

        # Process a Speaker-separated file
        if isSpeakerMode:
            # A segment is a blob of pronunciation and punctuation by an individual speaker
            for segment in data["results"]["speaker_labels"]["segments"]:

                # If there is content in the segment then pick out the time and speaker
                if len(segment["items"]) > 0:
                    # Pick out our next data
                    nextStartTime = float(segment["start_time"])
                    nextEndTime = float(segment["end_time"])
                    nextSpeaker = self.generateSpeakerLabel( str(segment["speaker_label"]))

                    # If we've changed speaker, or there's a 3-second gap, create a new row
                    if (nextSpeaker != lastSpeaker) or ((nextStartTime - lastEndTime) >= 3.0):
                        nextSpeechSegment = SpeechSegment()
                        speechSegmentList.append(nextSpeechSegment)
                        nextSpeechSegment.segmentStartTime = nextStartTime
                        nextSpeechSegment.segmentSpeaker = nextSpeaker
                        skipLeadingSpace = True
                        confidenceList = []
                        nextSpeechSegment.segmentConfidence = confidenceList
                    nextSpeechSegment.segmentEndTime = nextEndTime

                    # Note the speaker and end time of this segment for the next iteration
                    lastSpeaker = nextSpeaker
                    lastEndTime = nextEndTime

                    # For each word in the segment...
                    for word in segment["items"]:

                        # Get the word with the highest confidence
                        pronunciations = list(filter(lambda x: x["type"] == "pronunciation", data["results"]["items"]))
                        word_result = list(filter(lambda x: x["start_time"] == word["start_time"] and x["end_time"] == word["end_time"], pronunciations))
                        try:
                            result = sorted(word_result[-1]["alternatives"], key=lambda x: x["confidence"])[-1]
                            confidence = float(result["confidence"])
                        except:
                            result = word_result[-1]["alternatives"][0]
                            confidence = float(result["redactions"][0]["confidence"])

                        # Write the word, and a leading space if this isn't the start of the segment
                        if (skipLeadingSpace):
                            skipLeadingSpace = False
                            wordToAdd = result["content"]
                        else:
                            wordToAdd = " " + result["content"]

                        # If the next item is punctuation, add it to the current word
                        try:
                            word_result_index = data["results"]["items"].index(word_result[0])
                            next_item = data["results"]["items"][word_result_index + 1]
                            if next_item["type"] == "punctuation":
                                wordToAdd += next_item["alternatives"][0]["content"]
                        except IndexError:
                            pass

                        # Add word and confidence to the segment and to our overall stats
                        nextSpeechSegment.segmentText += wordToAdd
                        confidenceList.append({"Text": wordToAdd, "Confidence": confidence,
                                               "StartTime": float(word["start_time"]), "EndTime": float(word["end_time"])})
                        self.numWordsParsed += 1
                        self.cummulativeWordAccuracy += confidence

        # Process a Channel-separated file
        elif isChannelMode:

            # A channel contains all pronunciation and punctuation from a single speaker
            for channel in data["results"]["channel_labels"]["channels"]:

                # If there is content in the channel then start processing it
                if len(channel["items"]) > 0:

                    # We have the same speaker all the way through this channel
                    nextSpeaker = self.generateSpeakerLabel(str(segment["channel_label"]))
                    for word in channel["items"]:
                        # Pick out our next data from a 'pronunciation'
                        if word["type"] == "pronunciation":
                            nextStartTime = float(word["start_time"])
                            nextEndTime = float(word["end_time"])

                            # If we've changed speaker, or we haven't and the
                            # pause is very small, then start a new text segment
                            if (nextSpeaker != lastSpeaker) or ((nextSpeaker == lastSpeaker) and ((nextStartTime - lastEndTime) > 0.1)):
                                nextSpeechSegment = SpeechSegment()
                                speechSegmentList.append(nextSpeechSegment)
                                nextSpeechSegment.segmentStartTime = nextStartTime
                                nextSpeechSegment.segmentSpeaker = nextSpeaker
                                skipLeadingSpace = True
                                confidenceList = []
                                nextSpeechSegment.segmentConfidence = confidenceList
                            nextSpeechSegment.segmentEndTime = nextEndTime

                            # Note the speaker and end time of this segment for the next iteration
                            lastSpeaker = nextSpeaker
                            lastEndTime = nextEndTime

                            # Get the word with the highest confidence
                            pronunciations = list(filter(lambda x: x["type"] == "pronunciation", channel["items"]))
                            word_result = list(filter(lambda x: x["start_time"] == word["start_time"] and x["end_time"] == word["end_time"], pronunciations))
                            result = sorted(word_result[-1]["alternatives"], key=lambda x: x["confidence"])[-1]

                            # Write the word, and a leading space if this isn't the start of the segment
                            if (skipLeadingSpace):
                                skipLeadingSpace = False
                                wordToAdd = result["content"]
                            else:
                                wordToAdd = " " + result["content"]

                            # If the next item is punctuation, add it to the current word
                            try:
                                word_result_index = channel["items"].index(word_result[0])
                                next_item = channel["items"][word_result_index + 1]
                                if next_item["type"] == "punctuation":
                                    wordToAdd += next_item["alternatives"][0]["content"]
                            except IndexError:
                                pass

                            # Add word and confidence to the segment and to our overall stats
                            nextSpeechSegment.segmentText += wordToAdd
                            confidenceList.append({"Text": wordToAdd, "Confidence": float(result["confidence"]),
                                                   "StartTime": float(word["start_time"]), "EndTime": float(word["end_time"])})
                            self.numWordsParsed += 1
                            self.cummulativeWordAccuracy += float(result["confidence"])

            # Sort the segments, as they are in channel-order and not speaker-order, then
            # merge together turns from the same speaker that are very close together
            speechSegmentList = sorted(speechSegmentList, key=lambda segment: segment.segmentStartTime)
            speechSegmentList = self.mergeSpeakerSegments(speechSegmentList)

        # Inject sentiments into the segment list
        self.performComprehendNLP(speechSegmentList)

        # Return our full turn-by-turn speaker segment list with sentiment
        return speechSegmentList

    def calculateTranscribeConversationTime(self, filename):
        '''
        Tries to work out the conversation time based upon patterns in the filename.  Currently,
        the POC customer has this format - 0a.93.a0.3e.00.00-09.25.51.067-09-26-2019.wav, but there
        may be others, and hence this may need to be a plug-in per customer or something later.  If
        we cannot generate a time then the system later defaults to the current
        '''
        try:
            # Filename = 0a.93.a0.3e.00.00-09.25.51.067-09-26-2019.wav
            match = re.search('\d{2}.\d{2}.\d{2}.\d{3}-\d{2}-\d{2}-\d{4}', filename)
            self.conversationTime = str(datetime.strptime(match.group(), '%H.%M.%S.%f-%m-%d-%Y'))
        except:
            # Do nothing if everything fails - system will use "now" as the date
            pass

    def parseTranscribeFile(self, transcribeJob):
        """
        Parses the output from the specified Transcribe job
        """
        # Load in the Amazon Transcribe job header information, ensuring that the job has completed
        transcribe = self.getBoto3Client("transcribe")
        try:
            self.transcribeJobInfo = transcribe.get_transcription_job(TranscriptionJobName = transcribeJob)["TranscriptionJob"]
            assert self.transcribeJobInfo["TranscriptionJobStatus"] == "COMPLETED", f"Transcription job '{transcribeJob}' has not yet completed."
        except transcribe.exceptions.BadRequestException:
            assert False, f"Unable to load information for Transcribe job named '{transcribeJob}'."

        # Pick out the config parameters that we need
        outputS3Bucket = cf.appConfig[cf.CONF_S3BUCKET_OUTPUT]
        outputS3Key = cf.appConfig[cf.CONF_PREFIX_PARSED_RESULTS]

        # Work out the conversation time
        self.calculateTranscribeConversationTime(transcribeJob)

        # Download the job JSON results file to a local temp file - redacted if the job used it
        if self.transcribeJobInfo["ContentRedaction"]:
            uri = self.transcribeJobInfo["Transcript"]["RedactedTranscriptFileUri"]
        else:
            uri = self.transcribeJobInfo["Transcript"]["TranscriptFileUri"]
        offset = uri.find(outputS3Bucket) + len(outputS3Bucket) + 1
        self.jsonOutputFilename = uri[offset:]
        jsonFilepath = TMP_DIR + '/' + self.jsonOutputFilename
        s3Client = self.getBoto3Client('s3')
        s3Client.download_file(outputS3Bucket, self.jsonOutputFilename, jsonFilepath)

        # Now create turn-by-turn diarisation, with associated sentiments
        self.speechSegmentList = self.createTurnByTurnSegments(jsonFilepath)

        # Now go back over this and do custom entity detection, which can't be inline
        # as it's asynchronous and we need to do the whole conversation at once
        self.detectCustomEntities(self.jsonOutputFilename + ".plaintxt")

        # Write out the JSON data to our S3 location
        s3Resource = self.getBoto3Resource('s3')
        s3Object = s3Resource.Object(outputS3Bucket, outputS3Key + '/' + self.jsonOutputFilename)
        s3Object.put(
            Body=(bytes(json.dumps(self.outputAsJSON()).encode('UTF-8')))
        )
