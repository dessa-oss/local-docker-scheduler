"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""


class Queue(list):
    def __init__(self, *args, **kwargs):
        super(Queue, self).__init__(*args, **kwargs)

    def reposition(self, original_position, new_position):
        temp = self[original_position]
        del self[original_position]
        try:
            self.insert(new_position, temp)
        except IndexError:
            self.insert(original_position, temp)
            raise
