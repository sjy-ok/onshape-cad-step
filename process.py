# -*- coding: utf-8 -*-
import os
import yaml
import argparse
from joblib import delayed, Parallel
from myclient import MyClient
import time
import logging
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# 创建logs目录
logs_dir = "logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# 设置日志保存路径
log_filename = os.path.join(logs_dir, "process_log_{}.txt".format(time.strftime('%Y%m%d_%H%M%S')))

# 完全重置日志配置
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# 创建文件处理器
file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 获取根日志记录器并添加处理器
logger = logging.getLogger('')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 确认日志配置成功
logging.info("日志系统初始化完成，日志文件：{}".format(log_filename))

# 创建OnShape客户端实例
c = MyClient(logging=False)

def process_one_step(data_id, link, save_dir):
    """
    处理一个模型并导出为STEP格式文件
    
    Args:
        data_id (str): 数据ID
        link (str): OnShape链接
        save_dir (str): 保存目录
        
    Returns:
        tuple: (状态码, data_id, link)
            状态码：1表示成功，0表示失败
            data_id和link：仅在失败时返回，用于重新处理
    """

    # save_path = os.path.join(save_dir, "{}.step".format(data_id))
    # if os.path.exists(save_path):
    #     return 1

    v_list = link.split("/")
    did, wid, eid = v_list[-5], v_list[-3], v_list[-1]

    try:
        # 初始化STEP导出请求
        translation = c.translate_to_step(did, wid, eid)
        translation_id = translation['id']
        translation_name = translation['name']
        save_path = os.path.join(save_dir, "{}_{}.step".format(data_id, translation_name))
        
        # 轮询等待导出完成
        max_attempts = 30  # 最大尝试次数
        attempts = 0
        while True:
            if attempts >= max_attempts:
                logging.error("[{}] STEP导出超时".format(data_id))
                return 0, data_id, link

            status = c.get_translation_status(translation_id)
            if status['requestState'] == 'DONE':
                break
            elif status['requestState'] == 'FAILED':
                logging.error("[{}] STEP导出失败: {}".format(data_id, status.get('failureReason', '未知错误')))
                return 0, data_id, link
            
            time.sleep(2)  # 等待2秒后再次检查
            attempts += 1
        
        # 下载导出完成的STEP文件
        if status['resultExternalDataIds']:
            external_data_id = status['resultExternalDataIds'][0]
            response = c.download_external_data(did, external_data_id)
            with open(save_path, 'wb') as fp:
                fp.write(response.content)
            return 1, None, None
        else:
            logging.error("[{}] 没有找到ExternalDataId".format(data_id))
            return 0, data_id, link
            
    except Exception as e:
        logging.error("[{}] STEP导出出错: {}".format(data_id, str(e)))
        return 0, data_id, link


def save_failed_models(failed_models, batch_id, data_root, timestamp):
    """
    将处理失败的模型信息保存为YAML文件
    
    Args:
        failed_models (dict): 处理失败的模型信息，格式为 {data_id: link}
        batch_id (str): 批次ID
        data_root (str): 数据根目录
    """
    if not failed_models:
        return
    
    # 创建带时间戳的失败模型信息保存目录
    failed_dir = os.path.join(data_root, "failed_{}".format(timestamp))
    if not os.path.exists(failed_dir):
        os.makedirs(failed_dir)
    
    # 保存失败的模型信息 - 使用Python 2.7兼容的方式
    failed_path = os.path.join(failed_dir, "failed_models_{}.yml".format(batch_id))
    with open(failed_path, 'w') as fp:
        yaml.dump(failed_models, fp, allow_unicode=True)
    
    logging.info(u"已将失败的模型信息保存到 {}".format(failed_path))


parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="test with some examples")
parser.add_argument("--link_data_folder", default=None, type=str, help="data folder of onshape links from ABC dataset")
args = parser.parse_args()

if args.test:
    data_examples = {'00000352': 'https://cad.onshape.com/documents/4185972a944744d8a7a0f2b4/w/d82d7eef8edf4342b7e49732/e/b6d6b562e8b64e7ea50d8325',
                     '00001272': 'https://cad.onshape.com/documents/b53ece83d8964b44bbf1f8ed/w/6b2f1aad3c43402c82009c85/e/91cb13b68f164c2eba845ce6',
                     '00001616': 'https://cad.onshape.com/documents/8c3b97c1382c43bab3eb1b48/w/43439c4e192347ecbf818421/e/63b575e3ac654545b571eee6',
                    }

    # STEP导出
    save_dir = "examples_step"
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    for data_id, link in data_examples.items():
        print(data_id)
        process_one_step(data_id, link, save_dir)

else:
    DWE_DIR = args.link_data_folder
    DATA_ROOT = os.path.dirname(DWE_DIR)
    filenames = sorted(os.listdir(DWE_DIR))
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    for name in filenames:
        logging.info("====================================")
        batch_id = name.split('.')[0].split('_')[-1]
        logging.info("Processing batch: {}".format(batch_id))

        save_dir = os.path.join(DATA_ROOT, "processed/{}".format(batch_id))
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        dwe_path = os.path.join(DWE_DIR, name)
        with open(dwe_path, 'r') as fp:
            dwe_data = yaml.safe_load(fp)

        total_n = len(dwe_data)
        results = Parallel(n_jobs=10, verbose=2)(delayed(process_one_step)(data_id, link, save_dir)
                                            for data_id, link in dwe_data.items())
        
        # 处理结果
        success_count = sum(1 for result in results if result[0] > 0)
        failed_models = {result[1]: result[2] for result in results if result[0] == 0 and result[1] is not None}
        
        logging.info("valid/total: {}/{}".format(success_count, total_n))
        
        # 保存失败的模型信息
        if failed_models:
            logging.info(u"有 {} 个模型处理失败，正在保存信息".format(len(failed_models)))
            save_failed_models(failed_models, batch_id, DATA_ROOT, timestamp)