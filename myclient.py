# -*- coding: utf-8 -*-
from apikey.client import Client


class MyClient(Client):
    """
    继承自OnShape公共apikey Python客户端， 
    并增加了用于转换CAD格式的额外方法。
    """

    def translate_to_step(self, did, wid, eid):
        """
        异步导出STEP格式文件
        
        Args:
            - did (str): 文档ID
            - wid (str): 工作空间ID
            - eid (str): 元素ID
            
        Returns:
            - dict: 包含转换信息的响应数据
        """
        payload = {
            "allowFaultyParts": True,
            "angularTolerance": 0.001,
            "formatName": "STEP",
            "storeInDocument": False
        }
        
        response = self._api.request('post', 
                                    '/api/partstudios/d/' + did + '/w/' + wid + '/e/' + eid + '/translations',
                                    body=payload)
        return response.json()
    
    def get_translation_status(self, translation_id):
        """
        获取转换状态
        
        Args:
            - translation_id (str): 转换任务ID
            
        Returns:
            - dict: 包含转换状态的响应数据
        """
        response = self._api.request('get', '/api/translations/' + translation_id)
        return response.json()
    
    def download_external_data(self, did, fid):
        """
        下载外部数据
        
        Args:
            - did (str): 文档ID
            - fid (str): 外部数据ID
            
        Returns:
            - requests.Response: OnShape响应数据
        """
        headers = {
            'Accept': 'application/octet-stream'
        }
        return self._api.request('get', '/api/documents/d/' + did + '/externaldata/' + fid, headers=headers)
