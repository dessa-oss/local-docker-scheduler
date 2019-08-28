from app import app
import logging

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)

    app.run(use_reloader=False, host='0.0.0.0')
