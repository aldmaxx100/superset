Flock is a team messaging app(like slack).

This patch for superset lets you send your chart notification and alerts directly to flock.

You need to set following variables in your app config of superset.
AWS_ACCESS_KEY
AWS_SECRET_KEY
S3_BUCKET

The flock webhook url can be created via flock admin interface. It is essentially a incoming webhook.

To send a notification use slack box in reports interface and add flock webhook url in format(without quotes):

"webhook:url"

If you need to send to multiple flock channels, add in below format with "," as seperator.

"webhook:url1,url2"

CHEERS.
