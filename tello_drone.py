import socket
import threading
import cv2 as cv
import tello as tello


class Tello:
    """
    Manevrează conexiunea la drona DJI Tello
    """

    def __init__(self, local_ip, local_port, is_dummy=False, tello_ip='192.168.10.1', tello_port=8889):
        """
        Inițializează conexiunea cu Tello și trimite instrucțiuni de comandă și streamon
        pentru a porni și a începe să receptionati flux video.
        """
        self.background_frame_read = None
        self.response = None
        self.abort_flag = False
        self.is_dummy = is_dummy

        if not is_dummy:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            self.tello_address = (tello_ip, tello_port)
            self.local_address = (local_ip, local_port)

            self.send_command('command')
            # self.socket.sendto(b'command', self.tello_address)
            print('[INFO] Sent Tello: command')
            self.send_command('streamon')
            # self.socket.sendto(b'streamon', self.tello_address)
            print('[INFO] Sent Tello: streamon')
            self.send_command('takeoff')
            # self.socket.sendto(b'takeoff', self.tello_address)
            print('[INFO] Sent Tello: takeoff')
            self.move_up(100)

            # thread for receiving cmd ack
            self.receive_thread = threading.Thread(target=self._receive_thread)
            self.receive_thread.daemon = True

            self.receive_thread.start()

    def __del__(self):
        if not self.is_dummy:
            self.socket.close()

    def _receive_thread(self):
        while True:
            try:
                self.response, ip = self.socket.recvfrom(3000)
            except socket.error as exc:
                print(f"Caught exception socket.error: {exc}")

    def send_command(self, command):
        """
        Trimite o comandă către Tello și așteapta un răspuns.
        : param command: Comandă de trimis.
        : return (str): Răspuns de la Tello.
        """
        self.abort_flag = False
        timer = threading.Timer(0.5, self.set_abort_flag)

        self.socket.sendto(command.encode('utf-8'), self.tello_address)

        timer.start()
        while self.response is None:
            if self.abort_flag is True:
                break
        timer.cancel()

        if self.response is None:
            response = 'none_response'
        else:
            response = self.response.decode('utf-8')

        self.response = None

        return response

    def send_command_without_response(self, command):
        " Trimite o comandă fără să aștepte un răspuns. Util la trimiterea multor comenzi."
        if not self.is_dummy:
            self.socket.sendto(command.encode('utf-8'), self.tello_address)

    def set_abort_flag(self):
        self.abort_flag = True

    def move_up(self, dist):
        self.send_command_without_response(f'up {dist}')

    def move_down(self, dist):
        self.send_command_without_response(f'down {dist}')

    def move_right(self, dist):
        self.send_command_without_response(f'right {dist}')

    def move_left(self, dist):
        self.send_command_without_response(f'left {dist}')

    def move_forward(self, dist):
        self.send_command_without_response(f'forward {dist}')

    def move_backward(self, dist):
        self.send_command_without_response(f'back {dist}')

    def rotate_cw(self, deg):
        """
        "Trimite comenzi dronei pentru a se roti in sensul acelor de ceas"
        "param deg: numarul gradelor intre 0 si 360"
        "return str: raspunsul din partea dronei"
        """
        self.send_command_without_response(f'cw {deg}')

    def rotate_ccw(self, deg):
        """
       "Trimite comenzi dronei pentru a se roti in sensul acelor de ceas"
        "param deg: numarul gradelor intre 0 si 360"
        "return str: raspunsul din partea dronei"
        """
        self.send_command_without_response(f'ccw {deg}')

    def get_udp_video_address(self):
        """

        "Preia UDP construit pentru drona" \
        "return str : construtorul udp al adresei video"
        return f'udp://{self.tello_address[0]}:11111'
        """
    def get_frame_read(self):

        if self.background_frame_read is None:
            if self.is_dummy:
                self.background_frame_read = BackgroundFrameRead(self, 0).start()
            else:
                self.background_frame_read = BackgroundFrameRead(self, self.get_udp_video_address()).start()
        return self.background_frame_read

    def get_video_capture(self):
        """
        Obțineți obiectul VideoCapture de la drona camerei.
        - funcția return(VideoCapture): obiectul VideoCapture din fluxul video de la dronă
        """
        if self.cap is None:
            if self.is_dummy:
                self.cap = cv.VideoCapture(0)
            else:
                self.cap = cv.VideoCapture(self.get_udp_video_address())

        if not self.cap.isOpened():
            if self.is_dummy:
                self.cap.open(0)
            else:
                self.cap.open(self.get_udp_video_address())

        return self.cap

    def end(self):
        """
Se apelează această metodă atunci când se dorește terminarea obiectului Tello.        """
        # print(self.send_command('battery?'))
        if not self.is_dummy:
            self.send_command('land')
        if self.background_frame_read is not None:
            self.background_frame_read.stop()
        # It appears that the VideoCapture destructor releases the capture, hence when
        # attempting to release it manually, a segmentation error occurs.
        # if self.cap is not None:
        #     self.cap.release()


class BackgroundFrameRead:
    """
   Această clasă a citit cadrele dintr-un VideoCapture în fundal. Apoi, trebuie doar apelarea metodei
   backgroundFrameRead.frame pentru a obține pe cel real.
    """

    def __init__(self, tello, address):
        """
       Inițializează clasa Background Frame Read cu un VideoCapture
       al adresei specificate și primul frame citit.
        """
        tello.cap = cv.VideoCapture(address)
        self.cap = tello.cap

        if not self.cap.isOpened():
            self.cap.open(address)

        self.grabbed, self.frame = self.cap.read()
        self.stopped = False

    def start(self):
        """
        Pornește firul de citire a cadrului de fundal.
        : return (BackgroundFrameRead): Actualul BrackgroundFrameRead
        """
        threading.Thread(target=self.update_frame, args=()).start()
        return self

    def update_frame(self):
        """
        Setează cadrul curent la următorul cadru citit din sursă.
        """
        while not self.stopped:
            if not self.grabbed or not self.cap.isOpened():
                self.stop()
            else:
                (self.grabbed, self.frame) = self.cap.read()

    def stop(self):
        """
       Oprește citirea cadrului.
        """
        self.stopped = True
