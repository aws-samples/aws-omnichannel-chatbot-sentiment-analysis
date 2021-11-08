## Amazon Connect and Amazon Lex: Better Together

#### Deliver Omnichannel Customer Experiences with Interactive Voice Response (IVR) Enabled Contact Centers and Natural Language Processing (NLP) Chatbots – All Backed by Customer Sentiment Analysis

###### When is the last time you, as a customer, consumed a service or purchased a product? Did you interact with the service or product digitally or in-person? What if you had the flexibility to engage through multiple preferred channels (voice calls, digital chatbots, web-based interaction)? Your modern business is expected to deliver an omnichannel customer experience that unifies customer interactions across multiple channels into one seamless customer journey. Within Banking and Mortgage verticals, an omnichannel customer experience entails users availing all banking operations from a website, mobile application, physical branch location, call center, and other available channels, while context is maintained across all customer associations.

###### Iterating further on the seamless customer journey concept, you can derive customer sentiment from customer interconnections across your platforms. By identifying and extracting the relevant call and chat logs, website dwell times, and other pertinent source material, you develop a deep understanding of customer sentiment towards your services, products, employees, and more broadly, your brand, allowing you to iteratively improve the overall experience for your customers.

###### With Amazon Connect and Amazon Lex, you are able to offer your customers the flexible user experience they desire while maintaining a holistic view of their cross-platform engagement. By enabling customers with a self-service capability, you maximize the productivity of your call agents and skills-based work types while also minimizing the operational costs associated with human workforce supply.

#### Omnichannel User Interface Overview:

###### Once you navigate to the Mortgage Lender/Retail Bank’s AWS Amplify-powered website, you will see the below home screen with your Amazon Lex chatbot embedded within the bottom-right of your screen. The Amazon Lex chatbot then prompts the user for their 4-digit PIN before beginning to fulfill user intents. Let’s get started by building our Amazon Lex chatbot!

#### AWS Amplify website with embedded Amazon Lex chatbot:
<img width="1792" alt="Screen Shot 2021-11-02 at 9 51 06 AM" src="https://user-images.githubusercontent.com/73256380/139910925-c61977a5-1980-4360-9bb4-cb56a1f1718d.png">
 
#### 2-Part Omnichannel Deployment Process:
   
 1. Provision backend services through AWS CloudFormation 
 > (AWS Amplify, Amazon DynamoDB, Amazon Kendra, AWS Lambda, and Amazon S3).

 2. Import your Amazon Lex chatbot then integrate with Amazon Connect, Twilio SMS, and Slack.

#### The below architecture diagram illustrates your resultant solution architecture following the above deployment process:

 <img width="1792" alt="Screen Shot 2021-11-02 at 10 00 08 AM" src="https://user-images.githubusercontent.com/73256380/139911637-0a8c834f-2174-4bf4-b067-87c08be00bef.png">

#### Deployment Part-1: Provisioning backend services through AWS CloudFormation 
> (AWS Amplify, Amazon DynamoDB, Amazon Kendra, and AWS Lambda).

#### What are you deploying?

###### In Part-1 of your application architecture, you will build an Amazon Lex chatbot that understands customers' speech and text inputs. Your chatbot is embedded within a website created using AWS Amplify which is connected to the source repository that hosts our HTML, JavaScript, and CSS code. Data about available plans and users’ chosen plans are persisted in Amazon DynamoDB. AWS Lambda functions are triggered by Amazon Lex to execute business logic and interact with the database layer to query pertinent customer data and fulfill customer requests. Amazon Kendra also allows our chatbot to query against an indexed FAQ document so customers and call center agents can quickly find answers. You can also connect the Amazon Lex chatbot with Twilio SMS and Amazon Connect, which allows users to interact with your chatbot over SMS text messages and call your customer service number and interact with Amazon Lex’s Interactive Voice Response (IVR).

| **Region**   |  **Launch** |
|----------|:-------------:|
| Oregon (us-west-2) | <a target="_blank" href="https://us-west-2.console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/create/review?templateURL=https://omni-lex-artifacts.s3.us-west-2.amazonaws.com/omni-lex-cfn/omni-lex.yaml&stackName=omni-lex"><span><img height="24px" src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png"/></span></a> |

#### AWS CloudFormation Launch Instructions:

 1. Select the **Launch Stack** link above.
 2. Select **Next** on the Specify template page.
 3. Enter your \<STACK_NAME\> on the Specify stack details page and select **Next**.
 4. On the Configure stack options page, leave all the defaults and select **Next**.
 5. On the Review page, check all the boxes to acknowledge that CloudFormation will create IAM resources.
 6. Select **Create stack**.

Allow CloudFormation to launch your resources in the background; you do not need to wait for it to finish before proceeding to Deployment Part-2.

#### Deployment Part-2: Creating your Amazon Lex bot with Amazon Connect, Twilio SMS, and Slack integration through step-by-step guidance.

#### Amazon Lex Concepts:

- ###### Intent: An intent represents an action that the user wants to perform. You create a bot to support one or more related intents. For example, you might create a bot that orders pizza and drinks. For each intent, you provide the following required information:
  
  - ###### Intent name: A descriptive name for the intent. For example, _OrderPizza_. Intent names must be unique within your account.

  - ###### Sample utterances: How a user might convey the intent. For example, a user might say "Can I order a pizza please" or "I want to order a pizza".

  - ###### How to fulfill the intent: How you want to fulfill the intent after the user provides the necessary information (for example, place order with a local pizza shop). We recommend that you create a Lambda function to fulfill the intent. You can optionally configure the intent so Amazon Lex simply returns the information back to the client application to do the necessary fulfillment.
 
  ###### In addition to custom intents such as ordering a pizza, Amazon Lex also provides built-in intents to quickly set up your bot. For more information, see [Built-in Intents and Slot Types](https://docs.aws.amazon.com/lex/latest/dg/howitworks-builtins.html).
 
- ###### Slot: An intent can require zero or more slots or parameters. You add slots as part of the intent configuration. At runtime, Amazon Lex prompts the user for specific slot values. The user must provide values for all _required_ slots before Amazon Lex can fulfill the intent. For example, the _OrderPizza_ intent requires slots such as pizza size, crust type, and number of pizzas. In the intent configuration, you add these slots. For each slot, you provide slot type and a prompt for Amazon Lex to send to the client to elicit data from the user. A user can reply with a slot value that includes additional words, such as "large pizza please" or "let's stick with small." Amazon Lex can still understand the intended slot value.
 
  - ###### Slot type: Each slot has a type. You can create your custom slot types or use built-in slot types. Each slot type must have a unique name within your account. For example, you might create and use the following slot types for the _OrderPizza_ intent:
 
    - ###### Size: With enumeration values Small, Medium, and Large.
    - ###### Crust: With enumeration values Thick and Thin.

  ###### Amazon Lex also provides built-in slot types. For example, AMAZON.NUMBER is a built-in slot type that you can use for the number of pizzas ordered. For more information, see [Built-in Intents and Slot Types](https://docs.aws.amazon.com/lex/latest/dg/howitworks-builtins.html).

#### Amazon Lex Implementation:

Import Your Amazon Lex Chatbot:

1.  Navigate to the [Amazon Lex Console](https://console.aws.amazon.com/lex/home?region=us-east-1) and select the **Action** dropdown before selecting **Import**.
2.  Select **Browse** and choose the _omni-lex.zip_ file.
3.  Select the newly created _OmniLex_ under **Bots**.
4.  Select **FAQ** under **Intents** on the left menu and ensure the _Lex-Kendra-Index_ is selected under **Amazon Kendra query**. Also, ensure your **Response** section matches the below:
  
<img width="573" alt="Screen Shot 2021-11-02 at 10 46 47 AM" src="https://user-images.githubusercontent.com/73256380/139918404-c890060d-9ebb-43e8-aeeb-09b5fc79484b.png">

5. Select **MakePayment** under **Intents** on the left menu:

   - Under **Lambda initialization and validation**, select **Initialization and validation code hook** then choose your Lambda function _<STACK_NAME>-OmniLexHandler_ from the dropdown. The version or alias should be set to _Latest_. Select **OK** when prompted to give Amazon Lex permission to invoke your Lambda Function.

   - Under Fulfillment, select **AWS Lambda function** then choose your Lambda function _<STACK_NAME>-OmniLexHandler_ from the dropdown with the version or alias set to _Latest_.

6. Select **OpenAccount** under **Intents** on the left menu: 

   - Under **Lambda initialization and validation**, select **Initialization and validation code hook** then choose your Lambda function _<STACK_NAME>-OmniLexHandler_ from the dropdown. The version or alias should be set to _Latest_. Select **OK** when prompted to give Amazon Lex permission to invoke your Lambda Function.

   - Under **Fulfillment**, select **AWS Lambda function** then choose your Lambda function _<STACK_NAME>-OmniLexHandler_ from the dropdown with the version or alias set to _Latest_.

7. Select **ProvideAccountDetails** under **Intents** on the left menu: 

   - Under **Lambda initialization and validation**, select **Initialization and validation code hook** then choose your Lambda function _<STACK_NAME>-OmniLexHandler_ from the dropdown. The version or alias should be set to _Latest_. Select **OK** when prompted to give Amazon Lex permission to invoke your Lambda Function.

8. Select **VerifyIdentity** under **Intents** on the left menu: 

   - Under **Fulfillment**, select **AWS Lambda function** then choose your Lambda function _<STACK_NAME>-OmniLexHandler_ from the dropdown with the version or alias set to _Latest_. Select **OK** when prompted to give Amazon Lex permission to invoke your Lambda Function.

9. Select **Build** to assemble your chatbot, then test your chatbot using the dialogue box.

<img width="495" alt="Screen Shot 2021-11-02 at 11 50 30 AM" src="https://user-images.githubusercontent.com/73256380/139926946-05fdbc84-31ff-42fb-9742-fa1dca0cf568.png">

Configure Twilio SMS Integration with Your Amazon Lex Chatbot:

  1. [Create Twilio SMS Account](https://www.twilio.com/console).

To associate your Amazon Lex chatbot with your Twilio programmable SMS endpoint, we need to activate bot channel association in the Amazon Lex console. When the bot channel association has been activated, Amazon Lex returns a callback URL that we can use for Twilio SMS integration.

  2. Sign in to the [Amazon Lex Console](https://console.aws.amazon.com/lex/).
  3. Select _\<YOUR_BOUT_NAME\>_
  4. Navigate to the **Channels** tab.
  5. In the **Channels** section, select **Twilio SMS**.
  6. On the **Twilio SMS** page, provide the following information:

     - Channel name: LexTwilioAssociation
     - Select "aws/lex" from **KMS key**.
     - For **Alias**, select your bot alias.
     - For **Authentication Token**, enter the AUTH TOKEN for your Twilio account.
     - For **Account SID**, enter the ACCOUNT SID for your Twilio account.

  7. Select **Activate**.

The console creates the bot channel association and returns a Callback URL - Record this URL.

  8. On the [Twilio Console](https://www.twilio.com/console), navigate to **Programmable Messaging**.
  9. Select **Messaging Services**.
  10. Enter your Amazon Lex generated Callback URL into the **Request URL** field:
  
<img width="1135" alt="Screen Shot 2021-11-02 at 12 02 35 PM" src="https://user-images.githubusercontent.com/73256380/139928478-c2d1ca7d-bd8d-4b3f-a785-05738e32f197.png">

  11. Enter your Twilio-provided SMS number into the **Sender Pool**:

<img width="1116" alt="Screen Shot 2021-11-02 at 12 03 22 PM" src="https://user-images.githubusercontent.com/73256380/139928603-76f1a5f3-ff2a-40c8-8002-eea318867df4.png">

  12. Use your mobile phone to test the integration between Twilio SMS and your Amazon Lex chatbot by texting your Twilio-provided SMS number with a sample utterance.

<img width="920" alt="Screen Shot 2021-11-02 at 12 04 00 PM" src="https://user-images.githubusercontent.com/73256380/139928680-5a6bb796-41e7-4379-8c14-d43859aab2c6.png">

Configure Slack Integration with Your Amazon Lex Chatbot:

  1. [Sign Up for Slack and Create Slack Team](https://slack.com/help/articles/212675257-Join-a-Slack-workspace).

To associate your Amazon Lex chatbot with your Slack Application, we need to activate bot channel association in the Amazon Lex console. When the bot channel association has been activated, Amazon Lex returns a callback URL that we can use for Slack Application integration.

  2. [Create Slack application](https://docs.aws.amazon.com/lex/latest/dg/slack-bot-assoc-create-app.html).
     - Record your Client ID, Client Secret, and Verification Token.
  3. Sign in to the [Amazon Lex Console](https://console.aws.amazon.com/lex/).
  4. Select _\<YOUR_BOUT_NAME\>_
  5. Navigate to the **Channels** tab.
  6. In the **Channels** section, select **Slack**.
  7. On the **Slack** page, provide the following information:

     - Channel name: LexSlackAssociation
     - Select "aws/lex" from **KMS key**.
     - For **Alias**, select your bot alias.
     - For **Client Id**, enter the Client ID you recorded in Step-2.
     - For **Client Secret**, enter the Client Secret you recorded in Step-2.
     - For **Verification Token**, enter the Verification Token you recorded in Step-2.

  8.  Select **Activate**.
  9.  [Complete Slack application configuration](https://docs.aws.amazon.com/lex/latest/dg/slack-bot-back-in-slack-console.html).
  10. [Install your Slack application](https://docs.aws.amazon.com/lex/latest/dg/slack-bot-test.html) and use your Slack client to test the integration between Slack and your Amazon Lex chatbot by texting your Twilio-provided SMS number with a sample utterance.

<img width="1265" alt="Screen Shot 2021-11-02 at 12 18 16 PM" src="https://user-images.githubusercontent.com/73256380/139930521-104eba07-b4e4-4c61-bcbe-44e1bf54b7e6.png">

#### Customer Sentiment Analysis User Interface Overview:

###### Once you navigate to the Mortgage Lender/Retail Bank’s customer sentiment analysis dashboard, you will see the below home screen with a sortable list of your Amazon Connect call recordings and Amazon Lex transaction logs. Selecting one of the call recordings or transaction logs leads you to the subsequent screenshot which shows the interaction metadata, language used, average and trending caller and agent sentiment, call or chat duration, and a graph of caller and agent sentiment throughout the interaction. Let’s get started with our simple 3-step AWS CloudFormation deployment process!

#### Amazon QuickSight dashboard to list Amazon Lex transaction logs and Amazon Connect call recordings transcribed using Amazon Transcribe:
<img width="1792" alt="Screen Shot 2021-11-02 at 9 52 47 AM" src="https://user-images.githubusercontent.com/73256380/139910078-2b471e60-8ad1-42de-8858-44d347399ba9.png">

#### Amazon QuickSight dashboard to present Amazon Comprehend's customer sentiment analysis after transaction logs and call recordings are transcribed through AWS Step Functions workflow:
<img width="1792" alt="Screen Shot 2021-11-02 at 9 53 06 AM" src="https://user-images.githubusercontent.com/73256380/139910092-c93c34ac-b56f-47c1-b17c-2d3cc39c0ac0.png">

#### 3-Part Customer Sentiment Analysis Deployment Process:
   
1.  Create AWS Systems Manager Parameter Store by deploying AWS CloudFormation template and specifying AWS CloudFormation parameter values. 
2.  Provision backend services by installing code dependencies, creating AWS Lambda layer, then packaging and deploying AWS CloudFormation template ().
3.  Provision frontend customer sentiment analysis user-interface by installing code dependencies then packaging and deploying CloudFormation template ().

The below architecture diagram illustrates your resultant solution following the above deployment:

 <img width="1792" alt="Screen Shot 2021-11-02 at 12 22 23 PM" src="https://user-images.githubusercontent.com/73256380/139932191-8c6bc042-9596-4b5f-905e-ed01c4ee579a.png">

#### Deployment Part-1: Create AWS Systems Manager Parameter Store by deploying AWS CloudFormation template and specifying AWS CloudFormation parameter values. 

#### What are you deploying?

###### Part-1 of your customer sentiment analysis backend provisions AWS Systems Manager Parameter Store values that will used in subsequent deployment steps to identify variable like your call recording S3 Bucket name and the name of the S3 Bucket that will hold your transcribed call recordings.

| **Region**   |  **Launch** |
|----------|:-------------:|
| Oregon (us-west-2) | <a target="_blank" href="https://us-west-2.console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/create/review?templateURL=https://omni-lex-artifacts.s3.us-west-2.amazonaws.com/cfn/ssm.template&stackName=omni-lex-sentiment-ssm"><span><img height="24px" src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png"/></span></a> |

CloudFormation Launch Instructions:

1.  Select the **Launch Stack** link above.
2.  Select **Next** on the Specify template page.
3.  Enter _\<YOUR_STACK_NAME-\>_ on the Specify stack details page and select Next.
4.  On the Configure stack options page, leave all the defaults and select **Next**.
5.  On the Review page, check all the boxes to acknowledge that CloudFormation will create IAM resources.
6.  Select **Create stack**.

Wait for the _CREATE_COMPLETE_ status on your CloudFormation stack; you need to wait for it to finish before proceeding to Deployment Part-2.

| **Key** | **Default Value** | **Description** |
| --- | --- | --- |
| BulkUploadBucket | omni-lex-sentiment-bulk-upload | S3 Bucket into which bulk call recordings and chat transaction logs can be dropped – AWS Step Functions execution required for processing. |
| BulkUploadMaxDripRate | 50 | Maximum number of files that the bulk uploader will move to _ **InputBucketName** _per iteration. |
| BulkUploadMaxTranscribeJobs | 250 | Maximum number of concurrent Amazon Transcribe jobs (executing or queuing) bulk upload will execute. |
| ComprehendLanguages | en \| es \| fr \| de \| it \| pt \| ar \| hi \| ja \| ko \| zh \| zh-TW | Languages supported by Amazon Comprehend&#39;s standard calls, separated by &quot;|&quot; |
| ContentRedactionLanguages | en-US | Languages supported by Transcribe&#39;s Content Redaction feature, separated by \| |
| ConversationLocation | America/Los_Angeles | Name of the timezone location for the call source - this [is the ](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[**TZ database name** ](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[from ](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[https://en.wikipedia.or](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[g](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[/wiki/List](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[\_](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[of](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[\_](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[tz](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[\_](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[\_](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[time](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[\_](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)[zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| EntityRecognizerEndpoint | undefined | Name of the built custom entity recognizer for Amazon Comprehend (not including language suffix, e.g. -en). If one cannot be found then simple entity string matching is attempted. |
| EntityStringMap | simple-entity-list.csv | Basename of a CSV file containing item/Entity maps forwhen not enough data is present for Comprehend Custom Entities (not including language suffix, e.g. -en). |
| EntityThreshold | 0.5 | Confidence threshold where custom entity detection result is accepted. |
| InputBucketAudioPlayback | mp3 | Folder that holds browser audio playback. 
| InputBucketFailedTranscriptions | failedAudio | Folder that holds audio failed transcription files. |
| InputBucketName | omni-lex-sentiment-source-audio | S3 Bucket into which audio files are delivered. |
| InputBucketRawAudio | originalAudio | Folder that holds the raw call audio. |
| MaxSpeakers | 2 | Maximum number of speakers that are expected on a call. |
| MinSentimentNegative | 0.4 | Minimum sentiment level required to declare a phrase as having negative sentiment. |
| MinSentimentPositive | 0.4 | Minimum sentiment level required to declare a phrase as having positive sentiment. |
| OutputBucketName | omni-lex-sentiment-transcribe-output | S3 Bucket into which Amazon Transcribe output files are delivered. |
| OutputBucketParsedResults | parsedFiles | Folder within the output S3 Bucket into which parsed results are written. |
| SpeakerNames | Agent \| Caller | Default tags used for speaker names, separated by a \| |
| SpeakerSeparationType | Speaker | Separation mode for speakers, (speaker, channel, or auto). |
| StepFunctionName | PostCallAnalyticsWorkflow | Name of AWS Step Functions sentiment analysis workflow. |
| SupportFilesBucketName | omni-lex-sentiment-custom-source-files | S3 Bucket that hold supporting files, such as the file-based entity recognition mapping files. |
| TranscribeAlternateLanguage | en-US | Allows files delivered from a non-standard S3 Bucket to be based upon this language. |
| TranscribeLanguages | en-US | Language to be used for transcription - multiple entries separated by \| will trigger Language Detection using those languages; if that fails for any reason then the first language in this list is used for transcription. |
| VocabularyName | undefined | Name of the custom vocabulary to use for Amazon Transcribe (excluding language suffix). |

#### Deployment Part-2: Provision backend services by installing code dependencies, creating AWS Lambda layer, then packaging and deploying AWS CloudFormation template.

1.  Install code dependencies:

```
cd src/trigger
npm i

cd src/pca
pip install -t . -r requirements.txt
```
  
2.  Create and upload _ffmpeg.zip_ file to the S3 bucket defined in the configuration parameter _SupportFilesBucketName_ as specified in Part-1 of your customer sentiment analysis deployment:

 ```
mkdir layer
cd layer
mkdir bin
curl https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64- static.tar.xz | tar Jx
mv ffmpeg*/ffmpeg ffmpeg*/ffprobe bin zip -vr ffmpeg.zip bin -X
```

3.  Using the AWS CLI, enter the following to package and deploy your AWS CloudFormation template, replacing the below values:

| **Name** | **Value** |
| --- | --- |
| \<YOUR_BUCKET\> | Name of the S3 bucket that will hold packaged AWS Lambda code during deployment |
| \<STACK_NAME\> | Name of the CloudFormation stack |

```
cd cfn 

aws cloudformation package --template-file main.template \
   --output-template-file packaged.template \
   --s3-bucket <YOUR_BUCKET> 

aws cloudformation deploy --template-file packaged.template \
  --stack-name <YOUR_STACK> \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND 
```
  
#### Deployment Part-3: Provision frontend customer sentiment analysis user-interface by installing code dependencies then packaging and deploying CloudFormation template.

1.  Install code dependencies:

```
cd src/lambda
npm install
```
  
2.  Using the AWS CLI, enter the following to package and deploy your AWS CloudFormation template, replacing the below values:

| **Name** | **Value** |
| --- | --- |
| \<YOUR_BUCKET\> | Name of the S3 bucket in your account to store packaged AWS Lambda functions |
| \<STACK_NAME\> | Name of the CloudFormation stack |

```
cd cfn 

aws cloudformation package \
  --template-file main.template \ 
  --output-template-file packaged.template \ 
  --s3-bucket <YOUR_BUCKET> 

aws cloudformation deploy \
  --template-file packaged.template \
  --stack-name <STACK_NAME> \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND 
```

3. Add users to Cognito by navigating to the [Amazon Cognito console](https://console.aws.amazon.com/cognito/home?region=us-east-1) and locating the User Pool that was deployed by AWS CloudFormation in the previous step. Administrators will use these logins to access your customer sentiment analysis dashboard.

   - Go to **Users and Groups**.
   - Add users as required.

Your implementation is complete! You successfully deployed and configured the below architecture:

<img width="1792" alt="Screen Shot 2021-11-02 at 12 27 08 PM" src="https://user-images.githubusercontent.com/73256380/139935830-4f7a8e13-a8b5-42bb-8fd8-669b67b88e83.png">
