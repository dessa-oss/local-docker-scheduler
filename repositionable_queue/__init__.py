class Queue(list):
    def __init__(self, *args, **kwargs):
        super(Queue, self).__init__(*args, **kwargs)

    def reposition(self, original_position, new_position):
        temp = self[original_position]
        del self[original_position]
        self.insert(new_position, temp)
