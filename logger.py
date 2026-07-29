import logging

from schedule import logger
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'      )
logger = logging.getLogger(__name__)