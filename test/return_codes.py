import signal
import argparse
import sys
import time

g_return_code = 0


def exit_(sig_num, frame):
    print("Exiting...")
    global g_return_code
    sys.exit(g_return_code)


def main(time_, return_code):
    global g_return_code
    g_return_code = return_code
    signal.signal(signal.SIGFPE, exit_)  # signal.SIGFPE = 8
    time.sleep(time_)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-rc", "--return_code", type=int, default=0)
    parser.add_argument("-t", "--time", type=int, default=60)
    args = parser.parse_args()
    print(f"Signal: {signal.SIGFPE}, Time: {args.time}, Return Code: {args.return_code}")
    main(args.time, args.return_code)
