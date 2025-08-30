Read from a kafka topic
based on the value['msg_type'] which can be audio, document or text, process the message accordingly

if msg_type is audio, use the sarvam_translate function to translate the audio to text then resume the msg_text flow
if msg_type is document, create an S3 URL based on value and upload the document to S3, store the URI in DB

if msg_type is text:
infer user intent, which can be one of
- update conversational language
- view their details
- update their details
- ask for jobs

check if the concat of sender_id and receiver_id as the index_key are in the db.  
if index_key does not exist, infer the locale from the user text, and create a new entry.
if locale cannot be inferred, ask the user which language they want to converse in

if index_key exists in db, we need to ensure the following details need to exist.
basic profile:
- name
- age
- gender
- email
- location
- pin code
- spoken langugages

background:
- highest educational degree
- years of work experience
- currently employed
- notice period
- has a 2 wheeler

expectations:
- monthly salary
- job preferences: role, location, industry

use a function to determine which details in db are missing and return the ordered list.
If all details present, say you will get back with job details soon.
