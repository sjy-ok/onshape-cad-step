# -*- coding: utf-8 -*-
import os
import yaml
import argparse
from myclient import MyClient
import time
import logging
import glob
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

    # 检查是否存在STEP文件
    pattern = os.path.join(save_dir, "{}*".format(data_id))
    existing_files = glob.glob(pattern)
    if existing_files:
        # logging.info("[{}] 已存在STEP文件，跳过处理".format(data_id))
        return 1, data_id, link

    v_list = link.split("/")
    did, wid, eid = v_list[-5], v_list[-3], v_list[-1]

    try:
        # 初始化STEP导出请求
        translation = c.translate_to_step(did, wid, eid)
        translation_id = translation['id']
        translation_name = translation['name']
        translation_name = translation_name.replace('/', '-')  # 将斜杠替换为连字符
        save_path = os.path.join(save_dir, "{}_{}.step".format(data_id, translation_name))
        
        # 轮询等待导出完成
        max_attempts = 10  # 最大尝试次数
        attempts = 0
        start_time = time.time()
        absolute_timeout = 60  # 绝对超时时间，秒
        while True:
            if attempts >= max_attempts or time.time() - start_time > absolute_timeout:
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
        logging.info("===================================="*2)
        batch_id = name.split('.')[0].split('_')[-1]
        logging.info("Processing batch: {}".format(batch_id))

        save_dir = os.path.join(DATA_ROOT, "processed/{}".format(batch_id))
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        dwe_path = os.path.join(DWE_DIR, name)
        with open(dwe_path, 'r') as fp:
            dwe_data = yaml.safe_load(fp)

        total_n = len(dwe_data)
        
        # 创建失败模型记录文件路径
        failed_dir = os.path.join(DATA_ROOT, "failed_{}".format(timestamp))
        if not os.path.exists(failed_dir):
            os.makedirs(failed_dir)
        failed_path = os.path.join(failed_dir, "failed_models_{}.yml".format(batch_id))
        
        # 初始化失败模型字典，如果文件已存在则加载
        failed_models = {}
        if os.path.exists(failed_path):
            with open(failed_path, 'r') as fp:
                failed_models = yaml.safe_load(fp) or {}
        
        success_count = 0
        processed_count = 0
        need_update_failed = False
        
        # 获取所有ID并按递增顺序排序
        sorted_ids = sorted(dwe_data.keys())
        # logging.info(u"按ID递增顺序处理 {} 个模型".format(len(sorted_ids)))
        
        # 按排序后的ID顺序处理每个模型
        for data_id in sorted_ids:
            link = dwe_data[data_id]
            processed_count += 1
            result = process_one_step(data_id, link, save_dir)
            
            if result[0] > 0:
                success_count += 1
                # 每处理100个模型提醒一次进度，或者最后一个模型
                if processed_count % 100 == 0 or processed_count == total_n:
                    logging.info(u"------Current Progress: Valid/Total: {}/{} (Processed: {})".format(success_count, total_n, processed_count))
            else:
                # 模型处理失败，记录信息
                if result[1] is not None:
                    failed_models[result[1]] = result[2]
                    # logging.error(u"模型 {} 处理失败".format(data_id))
                    need_update_failed = True
            
            # 每处理100个模型更新一次失败记录，或者最后一个模型
            if (need_update_failed and processed_count % 100 == 0) or processed_count == total_n:
                if failed_models:
                    with open(failed_path, 'w') as fp:
                        yaml.dump(failed_models, fp, allow_unicode=True)
                    logging.info(u"√ Updated failed records, currently {} failed models".format(len(failed_models)))
                    need_update_failed = False
        
        logging.info(u"=======批次处理完成，成功/总数: {}/{}".format(success_count, total_n))
        
        # 在批次结尾列出失败模型的data_id
        if failed_models:
            failed_ids = failed_models.keys()
            logging.info(u"=======此批次共有 {} 个模型处理失败，失败模型ID: {}".format(
                len(failed_ids), ", ".join(failed_ids)))
        else:
            logging.info(u"=======此批次所有模型处理成功！！！")