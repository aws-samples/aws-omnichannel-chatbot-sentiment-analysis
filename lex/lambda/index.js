/*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

'use strict';

const AWS = require('aws-sdk');

const userDdbTable = process.env.USER_DDB_TABLE;
const userDdbTablePhoneIndex = process.env.USER_DDB_TABLE_PHONE_INDEX;
const userplansDdbTable = process.env.USER_PENDING_ACCOUNTS_DDB_TABLE;
const planCatalogueDdbTable = process.env.USER_EXISTING_ACCOUNTS_DDB_TABLE;

const stubUserId = "pendingUser";
const stubPin = "1234";

const helloIntentName = "Hello";
const applyPlanIntentName = "OpenAccount";
const checkPlanIntentName = "ProvideAccountDetails";
const verifyIdentityIntentName = "VerifyIdentity";
const listPlanIntentName = "ProvideAccountDetails";
const schedulePaymentIntentName = "MakePayment";
const finishIntentName = "Finish";

const followupQuestion = "How else can I help? You can say things like 'Check loan status' or 'What is my balance and due date?'";

const docClient = new AWS.DynamoDB.DocumentClient({
    region: process.env.AWS_REGION
});

const OctankAccountTypes = {
        'Accounts':{'types': ['Checking', 'Savings', 'Loan','checking','savings','loan']},
        'Actions':{'types': ['Check loan status', 'Refinance existing mortgage', 'Schedule a Payment', 'Open an Account']}
};

/*###########################################################################################################################################
#
#  Helpers to build responses based on customer utterances and defined Lex Intents & Slots.
#
###########################################################################################################################################*/
function nextIntent(sessionAttributes, message, responseCard, slots) {

    console.log(`nextIntent:  ${JSON.stringify(message)}`);
    return {
        sessionAttributes,
        dialogAction: {
            type: 'ElicitIntent',
            message: message,
            responseCard,
            slots,
        }
    };
}

function elicitSlot(sessionAttributes, intentName, slots, slotToElicit, message, responseCard) {
    return {
        sessionAttributes,
        dialogAction: {
            type: 'ElicitSlot',
            intentName,
            slots,
            slotToElicit,
            message,
            responseCard,
        },
    };
}

function confirmIntent(sessionAttributes, intentName, slots, message) {
    return {
        sessionAttributes,
        dialogAction: {
            type: 'ConfirmIntent',
            intentName,
            slots,
            message,
        },
    };
}

function close(sessionAttributes, fulfillmentState, message) {
    return {
        sessionAttributes,
        dialogAction: {
            type: 'Close',
            fulfillmentState,
            message,
        },
    };
}

function delegate(sessionAttributes, slots) {
    return {
        sessionAttributes,
        dialogAction: {
            type: 'Delegate',
            slots,
        },
    };
}


/*###########################################################################################################################################
#
#  Helpers to create response cards with multiple button options to streamline user experience.
#
###########################################################################################################################################*/

function buildResponseOptions(optionsArray = Array){
    var responseOptions = [];
    for(var i=0; i<optionsArray.length; i++){
        var temp = {
            "text": optionsArray[i],
            "value": optionsArray[i]
        }
        responseOptions.push(temp);
    }
    return responseOptions;
}

// Build a responseCard with a title, subtitle, and an optional set of options which should be displayed as buttons.
function buildResponseCard(title, subTitle, options) {
    let buttons = null;
    if (options !== null) {
        buttons = [];
        for (let i = 0; i < Math.min(5, options.length); i++) {
            buttons.push(options[i]);
        }
    }
    return {
        contentType: 'application/vnd.amazonaws.card.generic',
        version: 1,
        genericAttachments: [{
            title,
            subTitle,
            buttons,
        }],
    };
}

/*###########################################################################################################################################
#
#  Helpers to nullify capitalization variance in customer input and move userName from Session Attributes to Slot {userName}.
#
###########################################################################################################################################*/

function toUpper(str) {
    return str
        .toLowerCase()
        .split(' ')
        .map(function (word) {
            console.log("First capital letter: " + word[0]);
            console.log("remain letters: " + word.substr(1));
            return word[0].toUpperCase() + word.substr(1);
        })
        .join(' ');
}

function userNameSessiontoSlot(sessionAttributes, slots) {
    if (sessionAttributes.userName) {
        slots.userName = sessionAttributes.userName;
        // delete sessionAttributes.country;
    }
}

/*###########################################################################################################################################
#
#  Helpers to express when a customer's input results in a dead-end for the bot's logic.
#
###########################################################################################################################################*/

function errorResponse(callback, sessionAttributes) {
    callback(nextIntent(
        sessionAttributes,
        {
            'contentType': 'PlainText',
            'content': "Hmm3 that did not seem to work. " + followupQuestion
        }));
}

/*###########################################################################################################################################
#
#  Helpers to construct a date object in the local timezone by parsing the input date string, assuming a YYYY-MM-DD format.
#
###########################################################################################################################################*/

function parseLocalDate(date) {
    const dateComponents = date.split(/\-/);
    return new Date(dateComponents[0], dateComponents[1] - 1, dateComponents[2]);
}

function addWeeks(date, numberOfWeeks) {
    const newDate = parseLocalDate(date);
    newDate.setTime(newDate.getTime() + (86400000 * numberOfWeeks * 7));
    const paddedMonth = (`0${newDate.getMonth() + 1}`).slice(-2);
    const paddedDay = (`0${newDate.getDate()}`).slice(-2);
    return `${newDate.getFullYear()}-${paddedMonth}-${paddedDay}`;
}

/*###########################################################################################################################################
#
#  Helpers to validate customer input based on Octank Financial's parameters.
#
###########################################################################################################################################*/

function isValidDate(date) {
    try {
        if (isNaN(parseLocalDate(date).getTime())) {
            return false;
        }
        // start date must not be in the past.
        let timestamp = parseLocalDate(date).getTime();
        let now = (new Date()).getTime();
        return now <= timestamp;
    } catch (err) {
        return false;
    }
}

function buildValidationResult(isValid, violatedSlot, messageContent, slots, sessionAttributes) {
    return {
        isValid,
        violatedSlot,
        message: {contentType: 'PlainText', content: messageContent},
        slots,
        sessionAttributes
    };
}

function isValidUserName(userName) {
    var params = {
        TableName: planCatalogueDdbTable,
        KeyConditionExpression: 'userName = :c',
        ExpressionAttributeValues: {
            ':c': userName
        }
    };
    return new Promise((resolve, reject) => {
        docClient.query(params).promise().then(data => {
            if (data.Count !== 0) {
                resolve(true);
            } else {
                resolve(false);
            }
        }).catch(err => {
            console.error(err);
            reject(err);
        })
    });
}

function isValidNumOfWeek(numOfWeeks) {
    try {
        let num = parseInt(numOfWeeks);
        if (num <= 0 || num > 52) {
            return false;
        }
        return true;
    } catch (err) {
        return false;
    }
}

function isValidPlan(sessionAttributes, userName) {
    var flag = true;
    var params = {
        TableName: planCatalogueDdbTable,
        KeyConditionExpression: 'userName = :c',
        ExpressionAttributeValues: {
            ":c": userName
        }
    };
    docClient.query(params).promise().then(data => {
        for (var i = 0; i < data.Count; i++) {
            let item = data.Items[i];

            // For Loan accounts, we still are returning there are no Loan accounts belonging...
            if (!(item.planName === 'Loan' || item.planName === 'loan' || item.planName === 'Loans' || item.planName === 'loans')) {
                flag = false;
            }
        }
        return flag;
    }).catch(err => {
        console.error(err);
        errorResponse(callback, sessionAttributes);
    })
}

function validateApplyPlanInputs(sessionAttributes, slots, paymentFlag) {
    return new Promise((resolve, reject) => {
        userNameSessiontoSlot(sessionAttributes, slots);
        if (isValidUserName(slots.userName).then(isValid => {
                if (!isValid) {
                    resolve(buildValidationResult(false, 'userName', `Our records indicate there are no Accounts belonging to ${slots.userName}. What other User Names can we try? `), slots, sessionAttributes);
                } else {
                    sessionAttributes.userName = slots.userName;
                    if (slots.startDate != null && !isValidDate(slots.startDate)) {
                        resolve(buildValidationResult(false, 'startDate', `The date you specified, ${slots.startDate}, is not valid. Please specify an exact start date later than today.`), slots, sessionAttributes);
                    }

                    if (slots.numOfWeeks != null && !isValidNumOfWeek(slots.numOfWeeks)) {
                        resolve(buildValidationResult(false, 'numOfWeeks', `The number of weeks specified, ${slots.numOfWeeks}, before your next scheduled payment is not valid. Please specify an integer week(s) within the range: 1 to 52.`), slots, sessionAttributes);
                    }

                    //if (!isValidPlan(sessionAttributes, slots.userName) && paymentFlag) {
                      //  resolve(buildValidationResult(false, 'startDate', `Our records indicate there is no Loan Account belonging to ${slots.userName} and Loan accounts are the only type for which we accept payments. Please reply 'Open Loan Account' if you would like to begin the process. `), slots, sessionAttributes);
                    //}

                    resolve({isValid: true, sessionAttributes});
                }
            }).catch(err => reject(err)));
    });
}

/*###########################################################################################################################################
#
#  Helper to describe an existing Account with Octank Financial.
#
###########################################################################################################################################*/

function describePlan(item) {
    return item.planName + " Account " + " for " + item.userName +
        " opened " + item.startDate + " with next payment scheduled for " + item.endDate;
}

/*###########################################################################################################################################
#
#  Helpers to verify a user, confirm an already verified user, or return a logged-in/verified user.
#
###########################################################################################################################################*/

function requestUserVerification(callback, sessionAttributes) {
    callback(nextIntent(
        sessionAttributes,
        {
            'contentType': 'PlainText',
            'content': "Before we continue, please verify your identity. What's your user PIN?"
        }));
}

function isUserVerified(sessionAttributes) {
    if (sessionAttributes.identityVerified && (sessionAttributes.identityVerified === "true" || sessionAttributes.identityVerified === true )) {
        return true;
    } else {
        return false;
    }
}

function getVerifiedUser(sessionAttributes) {
    return sessionAttributes.loggedInUser;
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function finishIntent(intentRequest, callback) {
    const sessionAttributes = intentRequest.sessionAttributes || {};
    callback(close(sessionAttributes, 'Fulfilled', {
        contentType: 'PlainText',
        content: 'Thank you. Good bye.'
    }));
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function deliverPlan(slots, sessionAttributes, userActions, userName, data, callback, refinance) {
    sessionAttributes.userName = userName;
    var msg = `Thank you for choosing Octank Financial, ${userName}. `
    msg += "I see you have " + data.Count + " active Account" + (data.Count > 1 ? "s" : "") + " with us. ";

    for (var i = 0; i < data.Count; i++) {
        let item = data.Items[i];

        if (!(item.planName === 'Loan' || item.planName === 'loan' || item.planName === 'Loans' || item.planName === 'loans')) {
            msg += `Your current balance for your ${item.planName} Account is $${item.balance}. `
            if (item.pendingPayment === true) {
                msg += `You have a pending payment for the amount of $${item.paymentAmount}. `
            } else {
                msg += `You currently have no pending payments. `
            }
        } else {
            msg += `Your ${item.loanDuration}-year, $${item.loanAmount} at ${item.loanInterest}% interest Loan is ${(item.loanAmount-item.balance)/item.loanAmount*100}% paid off with a remaining balance of $${item.balance}. `
        }

        if (refinance == true) {
            msg += `\n\nWe can offer you a refinance for your remaining $${item.balance} balance at ${item.loanInterest - 0.10}% interest over 15 years - Please contact your Octank Financial client representative if you would like to discuss further 1-833-317-0315.`
        } else {
            msg += `Your next payment due date is ${item.dueDate}. `
        }
    }     

    msg += '\n\nHow else may I help you? ' 
    callback(nextIntent(
        sessionAttributes,
        {
            'contentType': 'PlainText',
            'content': msg
        }, buildResponseCard("How can I help?", "How can I help?", userActions)), slots);
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function helloIntent(intentRequest, callback) {
    const slots = intentRequest.currentIntent.slots;
    const sessionAttributes = intentRequest.sessionAttributes || {};
    var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);
    var userName = slots.userName

    if (intentRequest.sessionAttributes.userName) {
        slots.userName = sessionAttributes.userName
        userName = sessionAttributes.userName
    }

    if (slots.userName === null) {
        callback(elicitSlot(sessionAttributes, helloIntentName, userName, "userName", {
            'contentType': 'PlainText',
            'content': `Before we continue, please confirm the User Name attached to your Octank Financial profile. `
        }));
        return;
    }

    var params = {
        TableName: planCatalogueDdbTable,
        KeyConditionExpression: 'userName = :u',
        ExpressionAttributeValues: {
            ":u": userName
        }
    };
    docClient.query(params).promise().then(data => {
        console.log("list plan DDB result", JSON.stringify(data, null, 2));

        if (data.Count === 0) {
            callback(elicitSlot(sessionAttributes, listPlanIntentName, {userName: null}, "userName", {
                'contentType': 'PlainText',
                'content': `Our records indicate there are no Accounts belonging to ${userName}. What other User Names can we try? `
            }));
            return;
        }

        deliverPlan(slots, sessionAttributes, userActions, userName, data, callback, true);

    }).catch(err => {
        console.error(err);
        errorResponse(callback, sessionAttributes);
    })
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function listPlanIntent(intentRequest, callback) {
    const slots = intentRequest.currentIntent.slots;
    const sessionAttributes = intentRequest.sessionAttributes || {};
    var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);
    var userName = slots.userName

    if (intentRequest.sessionAttributes.userName) {
        slots.userName = sessionAttributes.userName
        userName = sessionAttributes.userName
    }

    if (slots.userName === null) {
        callback(elicitSlot(sessionAttributes, listPlanIntentName, userName, "userName", {
            'contentType': 'PlainText',
            'content': `Before we continue, please confirm the User Name attached to your Octank Financial profile. `
        }));
        return;
    }

    var params = {
        TableName: planCatalogueDdbTable,
        KeyConditionExpression: 'userName = :u',
        ExpressionAttributeValues: {
            ":u": userName
        }
    };
    docClient.query(params).promise().then(data => {
        console.log("list plan DDB result", JSON.stringify(data, null, 2));

        if (data.Count === 0) {
            callback(elicitSlot(sessionAttributes, listPlanIntentName, {userName: null}, "userName", {
                'contentType': 'PlainText',
                'content': `Our records indicate there are no Accounts belonging to ${userName}. What other User Names can we try? `
            }));
            return;
        }

        deliverPlan(slots, sessionAttributes, userActions, userName, data, callback, false);

    }).catch(err => {
        console.error(err);
        errorResponse(callback, sessionAttributes);
    })
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function applyPlan(slots, sessionAttributes, callback) {
    let userName = toUpper(slots.userName ? slots.userName : sessionAttributes.userName);
    let plan = slots.planName;
    var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);
    console.log("plan to apply: " + plan + " for country: " + userName);

    let user = getVerifiedUser(sessionAttributes);
    let startDate = slots.startDate;
    let numOfWeeks = parseInt(slots.numOfWeeks);
    let endDate = addWeeks(startDate, numOfWeeks);
    console.log("requested plan start date:", startDate, " ;end date:", endDate, " ;# of weeks:", numOfWeeks);

    var params = {
        TableName: userplansDdbTable,
        KeyConditionExpression: 'userId = :u and userName =:c',
        ExpressionAttributeValues: {
            ':u': user,
            ":c": userName
        }
    };
    docClient.query(params).promise().then(data => {
        for (var i = 0; i < data.Count; i++) {
            let item = data.Items[i];

            if (item.planName === plan) {
                callback(nextIntent(
                    sessionAttributes,
                    {
                        'contentType': 'PlainText',
                        'content': "You already have a " + plan + " Account under " + userName + ". Please see the following: " 
                        + describePlan(data.Items[0]) + ".\n\n" + followupQuestion
                    }, buildResponseCard("How can I help?", "How can I help?", userActions)));
            } 
        }
                
        let params = {
            TableName: userplansDdbTable,
            Item: {
                userId: user,
                userName: userName,
                planName: plan,
                startDate: startDate,
                endDate: endDate
            }
        };
        return docClient.put(params).promise();
    }).then(data => {
        // rely on the "Follow-up message" setting of the intent to confirm and follow-up
        callback(close(sessionAttributes, 'Fulfilled'));
    }).catch(err => {
        console.error(err);
        callback(nextIntent(
            sessionAttributes,
            {
                'contentType': 'PlainText',
                'content': "Thank you for opening an account. " + followupQuestion
            }, buildResponseCard("How can I help?", "How can I help?", userActions)));
    })
}

function applyPlanIntent(intentRequest, callback) {
    const slots = intentRequest.currentIntent.slots;
    const sessionAttributes = intentRequest.sessionAttributes || {};
    var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);

    // first check if the user identity verified
    if (!isUserVerified(sessionAttributes)) {
        sessionAttributes.intentBeforeVerification = applyPlanIntentName;
        if (slots.planName) {
            sessionAttributes.planToApply = slots.planName;
        }
        requestUserVerification(callback, sessionAttributes);
        return;
    }

    if (intentRequest.invocationSource === "DialogCodeHook") {

        // Check userName is supplied
        if (!slots.userName && !sessionAttributes.userName) {
            callback(elicitSlot(sessionAttributes, applyPlanIntentName, slots, "userName"));
        }

        // Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validateApplyPlanInputs(sessionAttributes, slots, false).then(validationResult => {
            if (!validationResult.isValid) {
                slots[`${validationResult.violatedSlot}`] = null;
                callback(elicitSlot(validationResult.sessionAttributes, intentRequest.currentIntent.name,
                    slots, validationResult.violatedSlot, validationResult.message));
                return;
            }
            callback(delegate(validationResult.sessionAttributes, slots));
        }).catch(err => {
            console.error(err);
            callback(nextIntent(
                sessionAttributes,
                {
                    'contentType': 'PlainText',
                    'content': "Hmm5 that did not seem to work. " + followupQuestion
                }, buildResponseCard("How can I help?", "How can I help?", userActions)));
        });
    } else {
        applyPlan(slots, sessionAttributes, callback);
    }
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function applyPayment(slots, sessionAttributes, callback) {
    let userName = toUpper(slots.userName ? slots.userName : sessionAttributes.userName);
    let plan = slots.planName;
    var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);
    console.log("plan to apply: " + plan + " for country: " + userName);

    let user = getVerifiedUser(sessionAttributes);
    let startDate = slots.startDate;
    let numOfWeeks = parseInt(slots.numOfWeeks);
    let endDate = addWeeks(startDate, numOfWeeks);
    console.log("requested plan start date:", startDate, " ;end date:", endDate, " ;# of weeks:", numOfWeeks);

    var params = {
        TableName: userDdbTable,
        KeyConditionExpression: 'userId = :u and userName =:c',
        ExpressionAttributeValues: {
            ':u': user,
            ":c": userName
        }
    };
    docClient.query(params).promise().then(data => {
        if (data.Count !== 0) {
            console.log(data);
            callback(nextIntent(
                sessionAttributes,
                {
                    'contentType': 'PlainText',
                    'content': "You already have a payment schedule for your " + plan + " Account. Please see the following: " 
                    + describePlan(data.Items[0]) + ".\n\n" + followupQuestion
                }, buildResponseCard("How can I help?", "How can I help?", userActions)));

        } else {
            let params = {
                TableName: userDdbTable,
                Item: {
                    // multiple pending account requests override each other - consider prefixing indices
                    userId: user,
                    userName: userName,
                    planName: plan,
                    startDate: startDate,
                    endDate: endDate
                }
            };
            return docClient.put(params).promise();
        }
    }).then(data => {
        // rely on the "Follow-up message" setting of the intent to confirm and follow-up
        callback(close(sessionAttributes, 'Fulfilled'));
    }).catch(err => {
        console.error(err);
        callback(nextIntent(
            sessionAttributes,
            {
                'contentType': 'PlainText',
                'content': "Thank you for scheduling your upcoming payment. " + followupQuestion
            }, buildResponseCard("How can I help?", "How can I help?", userActions)));
    })
}

function schedulePaymentIntent(intentRequest, callback) {
    const slots = intentRequest.currentIntent.slots;
    const sessionAttributes = intentRequest.sessionAttributes || {};
    var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);

    // first check if the user identity verified
    if (!isUserVerified(sessionAttributes)) {
        sessionAttributes.intentBeforeVerification = schedulePaymentIntentName;
        if (slots.planName) {
            sessionAttributes.planToApply = slots.planName;
        }
        requestUserVerification(callback, sessionAttributes);
        return;
    }

    if (intentRequest.invocationSource === "DialogCodeHook") {

        // Check userName is supplied
        if (!slots.userName && !sessionAttributes.userName) {
            //callback(elicitSlot(sessionAttributes, schedulePaymentIntentName, slots, "userName"));
        }

        // Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validateApplyPlanInputs(sessionAttributes, slots, true).then(validationResult => {
            if (!validationResult.isValid) {
                slots[`${validationResult.violatedSlot}`] = null;
                callback(elicitSlot(validationResult.sessionAttributes, intentRequest.currentIntent.name,
                    slots, validationResult.violatedSlot, validationResult.message));
                return;
            }
            callback(delegate(validationResult.sessionAttributes, slots));
        }).catch(err => {
            console.error(err);
            callback(nextIntent(
                sessionAttributes,
                {
                    'contentType': 'PlainText',
                    'content': "Hmm2 that did not seem to work. " + followupQuestion
                }, buildResponseCard("How can I help?", "How can I help?", userActions)));
        });
    } else {
        applyPayment(slots, sessionAttributes, callback);
    }
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function verifyIdentityIntent(intentRequest, callback) {
    var slots = intentRequest.currentIntent.slots;
    const sessionAttributes = intentRequest.sessionAttributes || {};

    verifyUser(sessionAttributes, slots, intentRequest).then(verifyUserResult => {
        if (verifyUserResult.result === true) {
            sessionAttributes.identityVerified = true;
            sessionAttributes.loggedInUser = verifyUserResult.userCognitoId;

            if (sessionAttributes.pinAttempt) {
                delete sessionAttributes.pinAttempt;
            }

            var accountTypes = buildResponseOptions(OctankAccountTypes['Accounts'].types);
            var userActions = buildResponseOptions(OctankAccountTypes['Actions'].types);
            var message = ''
            if (sessionAttributes.intentBeforeVerification === null || intentRequest.currentIntent.name === null) {
                message = "Thank you, we have verified your PIN. How can I help? You can say things like 'Check loan status' or 'What is my balance and due date?' ";
            } else {
                message = "Thank you, we have verified your PIN. How can I help? You can say things like 'Check loan status' or 'What is my balance and due date?' ";
            }
            
            if (sessionAttributes.intentBeforeVerification === applyPlanIntentName) {
                delete sessionAttributes.intentBeforeVerification;
                slots = {numOfWeeks: null, startDate: null, userName: null, planName: null};
                if (!sessionAttributes.userName) {
                    message += "You have asked to apply for an Account with Octank Financial. Can you please tell us your User Name? "
                    callback(elicitSlot(sessionAttributes, applyPlanIntentName, slots, 'userName', {
                        'contentType': 'PlainText',
                        'content': message
                    }));
                    return;
                } else {
                    userNameSessiontoSlot(sessionAttributes, slots);
                }

                if (sessionAttributes.planToApply) {
                    slots.planName = sessionAttributes.planToApply;
                    delete sessionAttributes.planToApply;
                    message += `You have asked to apply for a ${slots.planName} Account under ${slots.userName}'s account. When would you like the ${slots.planName} Account to begin? `
                    callback(elicitSlot(sessionAttributes, applyPlanIntentName, slots, 'startDate', {
                        'contentType': 'PlainText',
                        'content': message
                    }));
                    return;

                } else {
                    message += "You have asked to apply for an Account with Octank Financial. Would you like to open a Checking, Savings, or Loan Account? "
                    callback(elicitSlot(sessionAttributes, applyPlanIntentName, slots, 'planName', {
                        'contentType': 'PlainText',
                        'content': message
                    }, buildResponseCard(`${slots.userName}`, "Account Types", accountTypes)));
                    return;
                }
            } else if (sessionAttributes.intentBeforeVerification === checkPlanIntentName) {
                delete sessionAttributes.intentBeforeVerification;
                message += "You have asked to check your Accounts. "
                isValidPlan(sessionAttributes, message);
                return;
            } else if ((sessionAttributes.intentBeforeVerification === schedulePaymentIntentName)) {
                delete sessionAttributes.intentBeforeVerification;
                slots = {numOfWeeks: null, startDate: null, userName: null, planName: null};
                if (!sessionAttributes.userName) {
                    message += "You have asked to schedule a payment with Octank Financial. Can you please tell us your User Name? "
                    callback(elicitSlot(sessionAttributes, schedulePaymentIntentName, slots, 'userName', {
                        'contentType': 'PlainText',
                        'content': message
                    }));
                    return;
                } else {
                    userNameSessiontoSlot(sessionAttributes, slots);
                }

                if (sessionAttributes.planToApply) {
                    slots.planName = sessionAttributes.planToApply;
                    delete sessionAttributes.planToApply;
                    message += `You have asked to schedule a payment for a ${slots.planName} Account under ${slots.userName}'s account. When would you like the payment to occur? `
                    callback(elicitSlot(sessionAttributes, schedulePaymentIntentName, slots, 'startDate', {
                        'contentType': 'PlainText',
                        'content': message
                    }));
                    return;

                } else {
                    // might need to revert to "Checking, Savings, or Loan"
                    message += "You have asked to schedule a payment for an Account with Octank Financial. For which Account would you like to schedule the payment? "
                    callback(elicitSlot(sessionAttributes, schedulePaymentIntentName, slots, 'planName', {
                        'contentType': 'PlainText',
                        'content': message
                    }, buildResponseCard(`${slots.userName}`, "Account Types", accountTypes)));
                    return;
                }
            }

            callback(nextIntent(
                sessionAttributes,
                {
                    'contentType': 'PlainText',
                    'content': message
                }, buildResponseCard("How can I help?", "How can I help?", userActions)));

        } else {
            sessionAttributes.identityVerified = false;
            if (sessionAttributes.loggedInUser) {
                delete sessionAttributes.loggedInUser;
            }
            if (sessionAttributes.pinAttempt) {
                sessionAttributes.pinAttempt = parseInt(sessionAttributes.pinAttempt) + 1;
            } else {
                sessionAttributes.pinAttempt = 1;
            }
            if (sessionAttributes.pinAttempt > 3) {
                delete sessionAttributes.pinAttempt;
                callback(close(sessionAttributes, 'Failed',
                    {contentType: 'PlainText', content: "Unable to verify your identity. "}));
            } else {
                callback(elicitSlot(sessionAttributes, verifyIdentityIntentName, slots, "pin", {
                    contentType: 'PlainText',
                    content: "The pin did not match our records, please try again."
                }));
            }

        }
    }).catch(err => {
        callback(close(sessionAttributes, 'Failed',
            {contentType: 'PlainText', content: err.message}));
    })
}

/*###########################################################################################################################################
#
#  Intent: 
#
###########################################################################################################################################*/

function padPrecedingZeros(pinString) {
    if (pinString.length < 4) {
        var padded = "000" + pinString;
        return padded.slice(padded.length - 4);
    }
    else {
        return pinString;
    }
}

function verifyUser(sessionAttributes, slots, intentRequest) {
    return new Promise((resolve, reject) => {
        slots.pin = padPrecedingZeros(slots.pin);
        if (sessionAttributes.Source && sessionAttributes.Source === "AmazonConnect") {
            const phoneNumber = sessionAttributes.IncomingNumber;
            console.log("incoming phone number", phoneNumber)
            const expectedPin = phoneNumber.slice(phoneNumber.length - 4)
            if (slots.pin !== expectedPin) {
                console.log("pin mismatch", slots.pin, expectedPin);
                resolve({result: false});
            } else {
                resolve({result: true, userCognitoId: phoneNumber});
            }

            var params = {
                TableName: userDdbTable,
                IndexName: userDdbTablePhoneIndex,
                KeyConditionExpression: 'phone = :p',
                ExpressionAttributeValues: {
                   ':p': phoneNumber
                }
            };
            docClient.query(params).promise().then(data => {
                if (data.Count === 0) {
                   resolve(false);
                   return;
                }
                let item = data.Items[0];
                /* comment out because voice recognition of people's name is hard to get right (different spelling of same pronunciation, accents, etc.)
                let lastName = item['lastName']
                let firstName = item['firstName']
                let fullName = firstName.toLowerCase() + " " + lastName.toLowerCase()
                if (slots.name.toLowerCase() !== fullName) {
                    console.log("name does not match record. expected: [" + fullName + "] ; user input: [" + slots.name.toLowerCase() + "]");
                    resolve(false);
                    return;
                    //TODO : add KMS client side encryption of pin
                    if (slots.pin !== item.pin) {
                      console.log("pin mismatch");
                      resolve({result: false});
                      return;
                    }
                    resolve({result: true, userCognitoId: item.userId});*/
            }).catch(err => {
                console.error(err);
                reject(err);
            })
        }
        if (intentRequest.requestAttributes && intentRequest.requestAttributes["x-amz-lex:channel-type"] && intentRequest.requestAttributes["x-amz-lex:channel-type"] == "Twilio-SMS") {
            const phoneNumber = "+" + intentRequest.userId;
            console.log("incoming phone number", phoneNumber)
            const expectedPin = phoneNumber.slice(phoneNumber.length - 4)
            if (slots.pin !== expectedPin) {
                console.log("pin mismatch", slots.pin, expectedPin);
                resolve({result: false});
            } else {
                resolve({result: true, userCognitoId: phoneNumber});
            }
        } else {
            // from lex console, no phone number to identity the user.
            if (slots.pin !== stubPin) {
                console.log("No phone number from input, pin mismatch stub pin");
                resolve({result: false});
                return;
            } else {
                console.log("No phone number from input, pin match stub pin")
                if (intentRequest.requestAttributes && intentRequest.requestAttributes["x-amz-lex:channel-type"] && intentRequest.requestAttributes["x-amz-lex:channel-type"] == "Facebook") {
                    if (intentRequest.requestAttributes['x-amz-lex:user-id']) {
                        resolve({result: true, userCognitoId: intentRequest.requestAttributes['x-amz-lex:user-id']});
                        return;
                    }
                }
                resolve({result: true, userCognitoId: stubUserId});
            }
        }
    });
}

/*###########################################################################################################################################
#
#  Handler/Dispatch/Logging: Determine how to route incoming requests, invoked when customer specifies an intent.
#
###########################################################################################################################################*/

exports.handler = (event, context, callback) => {


    try {
        // By default, treat the user request as coming from the US west coast time zone.
        process.env.TZ = 'America/Los_Angeles';
        //console.log(`event.bot.name=${event.bot.name}`);

        /**
         * Uncomment this if statement and populate with your Lex bot name, alias and / or version as
         * a sanity check to prevent invoking this Lambda function from an undesired source.
         */
        // if (event.bot.name != botName) {
        //     callback('Invalid Bot Name');
        // }
        // dispatch(event, (response) => callback(null, response));
        dispatch(event, (response) => loggingCallback(response, callback));
    } catch (err) {
        callback(err);
    }
};

function dispatch(intentRequest, callback) {

    //console.log(JSON.stringify(intentRequest, null, 2));
    //console.log(`dispatch userId=${intentRequest.userId}, intentName=${intentRequest.currentIntent.name}`);

    const intentName = intentRequest.currentIntent.name;

    // Dispatch to your skill's intent handlers
    if (intentName === helloIntentName){
        return helloIntent(intentRequest, callback);
    } else if (intentName === verifyIdentityIntentName) {
        return verifyIdentityIntent(intentRequest, callback);
    } else if (intentName === applyPlanIntentName) {
        return applyPlanIntent(intentRequest, callback);
    } else if (intentName === finishIntentName) {
        return finishIntent(intentRequest, callback);
    } else if (intentName === listPlanIntentName) {
        return listPlanIntent(intentRequest, callback);
    } else if (intentName === schedulePaymentIntentName) {
        return schedulePaymentIntent(intentRequest, callback);
    }
    throw new Error(`Intent with name ${intentName} not supported`);
}


function loggingCallback(response, originalCallback) {
    console.log("lambda response:\n", JSON.stringify(response, null, 2));
    originalCallback(null, response);
}
