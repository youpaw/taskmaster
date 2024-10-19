import signal
import argparse
import sys
import time

g_return_code = 0


def exit_(sig_num, frame):
    print("Exiting...")
    global g_return_code
    sys.exit(g_return_code)

def hello(sig_num, frame):
    print("Hello! I'm alive!")


def main(signal_, time_, return_code):
    global g_return_code
    g_return_code = return_code
    if signal_ == 8:
        signal.signal(signal.SIGFPE, exit_)  # signal.SIGFPE = 8
    elif signal_ == 10:
        signal.signal(signal.SIGUSR1, hello)  # signal.SIGUSR1 = 10
    time.sleep(time_)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-rc", "--return_code", type=int, default=0)
    parser.add_argument("-t", "--time", type=int, default=60)
    parser.add_argument("-s", "--signal", type=int, default=8)
    args = parser.parse_args()
    print(f"Signal: {args.signal}, Time: {args.time}, Return Code: {args.return_code}")
    main(args.signal, args.time, args.return_code)
