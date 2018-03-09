from gevent import monkey
monkey.patch_all()
import argparse
import logging
import signal
import gevent
import gevent.queue
import actor
import checker


def end_proc(mailbox):
    mailbox.get()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', type=str, help='Url to check.')
    parser.add_argument('--rate', type=float, default=10,
                        help='Requests per second. Defaults to 10.')
    parser.add_argument('--user-agent', type=str, default='LinkChecker/dev',
                        help=('User agent header for requests. '
                              'Defaults to "LinkChecker/dev".'))
    dev_group = parser.add_mutually_exclusive_group()
    dev_group.add_argument('--dev', dest='dev', action='store_true',
                           help='Run in dev mode.')
    dev_group.add_argument('--no-dev', dest='dev', action='store_false',
                           help="Don't run in dev mode. Default mode.")
    parser.set_defaults(dev=False)
    args = parser.parse_args()

    if args.dev:
        logging.basicConfig(level=logging.DEBUG)

    end_mailbox = gevent.queue.Queue()

    create_pulse = (lambda parent: actor.spawn(checker.Pulse,
                                               parent=parent,
                                               rate=1 / args.rate))
    create_fetcher = (lambda parent:
                      actor.spawn(checker.Fetcher,
                                  parent=parent,
                                  user_agent=args.user_agent,
                                  base_url=args.url))
    (actor.spawn(checker.Checker,
                 base_url=args.url,
                 end_mailbox=end_mailbox,
                 create_pulse=create_pulse,
                 create_fetcher=create_fetcher)
     .run())

    gevent.joinall([gevent.spawn(end_proc, end_mailbox)])
