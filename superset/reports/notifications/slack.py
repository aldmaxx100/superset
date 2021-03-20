# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import json
import logging
from io import IOBase
from typing import Optional, Union
import random

from flask_babel import gettext as __
from retry.api import retry
from slack import WebClient
from slack.errors import SlackApiError, SlackClientError
import requests
import boto3
from superset import app
from superset.models.reports import ReportRecipientType
from superset.reports.notifications.base import BaseNotification
from superset.reports.notifications.exceptions import NotificationError

logger = logging.getLogger(__name__)


class SlackNotification(BaseNotification):  # pylint: disable=too-few-public-methods
    """
    Sends a slack notification for a report recipient
    """

    type = ReportRecipientType.SLACK

    def _get_channel(self) -> str:
        return json.loads(self._recipient.recipient_config_json)["target"]

    @staticmethod
    def _error_template(name: str, text: str) -> str:
        return __(
            """
            *%(name)s*\n
            Error: %(text)s
            """,
            name=name,
            text=text,
        )

    def _get_body(self) -> str:
        if self._content.text:
            return self._error_template(self._content.name, self._content.text)
        if self._content.screenshot:
            return __(
                """
                *%(name)s*\n
                <%(url)s|Explore in Superset>
                """,
                name=self._content.name,
                url=self._content.screenshot.url,
            )
        return self._error_template(self._content.name, "Unexpected missing screenshot")

    def _get_inline_screenshot(self) -> Optional[Union[str, IOBase, bytes]]:
        if self._content.screenshot:
            return self._content.screenshot.image
        return None





    def send(self) -> None:
        if self.sendToWebhook():
            logging.info("Report sent to flock")
            return
        file = self._get_inline_screenshot()
        channel = self._get_channel()
        body = self._get_body()
        try:
            token = app.config["SLACK_API_TOKEN"]
            if callable(token):
                token = token()
            client = WebClient(token=token, proxy=app.config["SLACK_PROXY"])
            # files_upload returns SlackResponse as we run it in sync mode.
            if file:
                client.files_upload(
                    channels=channel, file=file, initial_comment=body, title="subject",
                )
            else:
                client.chat_postMessage(channel=channel, text=body)
            logger.info("Report sent to slack")
        except SlackClientError as ex:
            raise NotificationError(ex)


    def uploadAndPresign(self):
        try:
            file = self._get_inline_screenshot()

            s3 = boto3.client(service_name='s3',
                                aws_access_key_id=app.config['IMEDIA_AWS_ACCESS_KEY'],
                                aws_secret_access_key=app.config['IMEDIA_AWS_SECRET_KEY'])
            choices = [chr(i + 97) for i in range(26)]
            choosed = [random.choice(choices) for i in
                       range(random.choice([5, 6, 7, 8, 9, 10]))]
            filename=''.join(choosed)
            s3.put_object(Body=file, Bucket=app.config['IMEDIA_SUPERSET_BUCKET'],
                                       Key=filename)
            response = s3.generate_presigned_url('get_object',
                                                             Params={
                                                                 'Bucket': app.config['IMEDIA_SUPERSET_BUCKET'],
                                                                 'Key': filename},

                                                             ExpiresIn=3600)

            return response
        except Exception as e:
            logging.error(e.__str__())
            raise Exception('Error in Presignning url generation')

    def generatePayload(self,preSignedUrl):

        try:
            send_template = {
                'text': '',

                'attachments': [{
                    'title': "",
                    'views': {
                        "image": {
                            "original": {
                                "src": "",
                                "width": 400, "height": 400}
                        }
                    }
                }]
            }

            alertname = self._content.name
            url = self._content.screenshot.url
            send_template['text']=url+'|Explore More in SuperSet'
            send_template['attachments'][0]['title']=alertname
            send_template['attachments'][0]['views']['image']['original']['src']=preSignedUrl
            return send_template
        except Exception as e:
            logging.error(e.__str__())
            raise Exception('Error in Generating payload')


    def sendToFlock(self,flockUrl,payload):
        try:
            count=0
            while count<=5:
                response=requests.post(flockUrl,json=payload)
                if response.status_code==200:
                    logging.info('Flock alert sent successfully')
                    break
                else:
                    count+=1



        except Exception as e:
            logging.error(e.__str__())




    def sendToWebhook(self):
        try:
            channel=self._get_channel()
            if 'webhook:'==channel[:8]:
                preSignedUrl=self.uploadAndPresign()
                payload=self.generatePayload(preSignedUrl)

                flockurl=channel[8:].split(',')

                for flock in flockurl:
                    self.sendToFlock(flock,payload)


                return True
            else:
                return False
        except Exception as e:
            logging.error(e.__str__())
            return False






