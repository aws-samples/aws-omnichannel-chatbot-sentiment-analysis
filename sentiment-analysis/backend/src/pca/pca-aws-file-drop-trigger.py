import json
import urllib.parse
import boto3
import pcaconfiguration as cf

# Mime audio type mappings
mimeAudioMapping = {'audio/wav': 'wav', 'audio/mp4': 'mp4', 'audio/x-flac': 'flac', 'audio/flac': 'flac', 'audio/mpeg': 'mp3', 'audio/mp3': 'mp3'}


def lambda_handler(event, context):
    # Load our configuration
    cf.loadConfiguration()
    print("S3 Event: " + str(event["Records"][0]))

    # Get the object from the event and validate its content type
    s3 = boto3.client("s3")
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except Exception as e:
        print(e)
        raise Exception(
            'Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(
                key, bucket))

    # Extract the parameters, and also validate that the content type is supported
    mimeFormat = response['ContentType']

    if mimeFormat not in mimeAudioMapping:
        raise Exception(
            'Cannot parse files of type {} - only the audio formats wav, mp3, mp4 and flac are supported.'.format(mimeFormat))
    else:
        mediaFormat = mimeAudioMapping[mimeFormat]

    # Check a Transcribe job isn't in progress for this file-name
    jobName = cf.generateJobName(key)
    try:
        # If it exists (e.g. doesn't exception) then we may want to delete iz
        transcribe = boto3.client('transcribe')
        currentJobStatus = transcribe.get_transcription_job(TranscriptionJobName=jobName)["TranscriptionJob"]["TranscriptionJobStatus"]
    except Exception as e:
        # Job didn't already exist - no problem here
        currentJobStatus = ""

    # If there's a job already running then the input file may have been copied - quit
    if (currentJobStatus == "IN_PROGRESS") or (currentJobStatus == "QUEUED"):
        # Throw an exception if this is the case
        raise Exception(
            'A Transcription job named \'{}\' is already in progress - cannot continue.'.format(jobName))

    # Now find our Step Function
    ourStepFunction = cf.appConfig[cf.COMP_SFN_NAME]
    sfnClient = boto3.client('stepfunctions')
    response = sfnMachinesResult = sfnClient.list_state_machines(maxResults = 1000)
    sfnArnList = list(filter(lambda x: x["stateMachineArn"].endswith(ourStepFunction), sfnMachinesResult["stateMachines"]))
    if sfnArnList == []:
        # Doesn't exist
        raise Exception(
            'Cannot find configured Step Function \'{}\' in the AWS account in this region - cannot begin workflow.'.format(ourStepFunction))
    sfnArn = sfnArnList[0]['stateMachineArn']

    # Decide what language this should transcribed in.  The logic is:
    # SSM:TranscribeLanguages == {2+ languages} => Transcribe Language Detection [blank lang-code]
    # SSM:InputBucketName == {S3 trigger bucket} => SSM:TranscribeLanguages
    # => SSM:TranscribeAlternateLanguage
    transcribeLanguage = ""
    if not cf.isAutoLanguageDetectionSet():
        if bucket == cf.appConfig[cf.CONF_S3BUCKET_INPUT]:
            transcribeLanguage = cf.appConfig[cf.CONF_TRANSCRIBE_LANG][0]
        else:
            transcribeLanguage = cf.appConfig[cf.CONF_TRANSCRIBE_ALTLANG]

    # Trigger a new Step Function execution
    parameters = '{\n  \"bucket\": \"' + bucket + '\",\n' +\
                 '  \"key\": \"' + key + '\",\n' +\
                 '  \"contentType\": \"' + mediaFormat + '\",\n' + \
                 '  \"langCode\": \"' + transcribeLanguage + '\"\n' +\
                 '}'
    sfnClient.start_execution(stateMachineArn = sfnArn, input = parameters)

    # Everything was successful
    return {
        'statusCode': 200,
        'body': json.dumps('Post-call analytics workflow for file ' + key + ' successfully started.')
    }

# Main entrypoint
if __name__ == "__main__":
    event = {
        "Records": [
            {
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "eca58aa9-dd2b-4405-94d5-d5fba7fd0a16",
                    "bucket": {
                        "name": "pca-custom-source-files",
                        "ownerIdentity": {
                            "principalId": "A39I0T5T4Z0PZJ"
                        },
                        "arn": "arn:aws:s3:::pca-raw-audio-1234"
                    },
                    "object": {
                        "key": "nci/0a.93.a0.3e.00.00 09.11.32.483 09-10-2019.wav",
                        "size": 963023,
                        "eTag": "8588ee73ae57d72c072f4bc401627724",
                        "sequencer": "005E99B1F567D61004"
                    }
                }
            }
        ]
    }
    lambda_handler(event, "")

    # "name": "pca-raw-audio-1234",
    # "key": "nci/0a.93.a0.3a.00.00 15.28.03.654 03-13-2020.wav",
