class GoBackNSocket:

    def __init__(self):
        self.data = []

    def receive(self, packet):
        print("erhalte packet: ", packet.decode("utf-8"))
