import json
import os
from openai import OpenAI


class NewsEventExtractor:
    def __init__(self, api_key=None, base_url="https://api.vectorengine.ai/v1", timeout=120):
        """
        初始化新闻事件提取器
        
        Args:
            api_key (str): API密钥，默认使用内置密钥
            base_url (str): API基础URL
            timeout (int): 请求超时时间
        """
        if api_key is None:
            api_key = 'sk-bRwTYwT9qN23LDZDD4WlwNyll788tBgtuDuqQTXRtFGjaGQY'
            
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout
        )
        
    def extract_events(self, news_text):
        """
        从新闻文本中提取事件信息
        
        Args:
            news_text (str): 新闻文本内容
            
        Returns:
            dict: 提取的事件信息，如果解析失败则返回原始输出
        """
        # 系统提示词定义
        system_prompt = """现在是2025年，你是一个专注于中文财经新闻的事件抽取器。输入是一条关于中国上市公司的新闻、公告或研报摘录。请严格按 JSON 输出，注意不要带多余文本。要求输出字段（必须包含）：
                - ticker: 若能识别请写股票代码（如 600519）；否则写 null
                - company: 公司名称或 null
                - company_confidence: 公司名称置信度，0.0 到 1.0，这个参数表明这篇文章是否指向某一个公司，若指向则置信度高，否则置信度低
                - event_type: 从以下列表中选择一个或多个（policy_change, earnings, ipo, delisting,
                share_issuance, acquisition, merger, regulation, approval, clinical_trial, executive_change,
                large_holder_trade, financing, other）
                - summary: 1-2 句中文摘要（简洁）
                - event_date: 文本中能识别出的关键日期（ISO 格式 YYYY-MM-DD），否则 null
                - impact_direction: one of [positive, neutral, negative, unknown]
                - impact_score: 一个 -1.0 到 1.0 的浮点（代表 LLM 的即时影响判断）
                - confidence: 0.0 到 1.0（模型对识别结果的置信度）
                - tags: 关键词数组（如 ['并购','重组','监管']）"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {"role": "user", "content": news_text}
                ]
            )
            
            # 获取模型输出内容
            raw_output = response.choices[0].message.content
            
            # 尝试解析为 JSON
            try:
                parsed = json.loads(raw_output)
                return parsed
            except json.JSONDecodeError:
                # 如果解析失败，返回原始输出
                return {
                    "success": False,
                    "raw_output": raw_output,
                    "error": "Model output is not valid JSON"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def extract_events_to_model(self, news_text):
        """
        从新闻文本中提取事件信息并返回模型响应对象
        
        Args:
            news_text (str): 新闻文本内容
            
        Returns:
            object: 完整的模型响应对象
        """
        # 系统提示词定义
        system_prompt = """你是一个专注于中文财经新闻的事件抽取器。输入是一条关于中国上市公司的新闻、公告或研报摘录。请严格按 JSON 输出，注意不要带多余文本。要求输出字段（必须包含）：
                - ticker: 若能识别请写股票代码（如 600519）；否则写 null
                - company: 公司名称或 null
                - company_confidence: 公司名称置信度，0.0 到 1.0，这个参数表明这篇文章是否指向某一个公司，若指向则置信度高，否则置信度低
                - event_type: 从以下列表中选择一个或多个（policy_change, earnings, ipo, delisting,
                share_issuance, acquisition, merger, regulation, approval, clinical_trial, executive_change,
                large_holder_trade, financing, other）
                - summary: 1-2 句中文摘要（简洁）
                - event_date: 文本中能识别出的关键日期（ISO 格式 YYYY-MM-DD），否则 null
                - impact_direction: one of [positive, neutral, negative, unknown]
                - impact_score: 一个 -1.0 到 1.0 的浮点（代表 LLM 的即时影响判断）
                - confidence: 0.0 到 1.0（模型对识别结果的置信度）
                - tags: 关键词数组（如 ['并购','重组','监管']）"""
        
        response = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {"role": "user", "content": news_text}
            ]
        )
        
        return response


# 使用示例
if __name__ == "__main__":
    # 示例新闻文本
    news = """凤凰网财经《公司研究院》

订单增长放缓，小米中国区紧急做出系列人事变动，涉及手机、汽车、大家电业务。

12月9日，据媒体报道，原销售运营一部总经理一职由小米集团高级副总裁，中国区总裁王晓雁兼任；任命江苏分公司总经理郭金保担任销售运营二部总经理，向王晓雁汇报，同时郭金保继续兼任江苏分公司总经理。

原小米汽车部销交服部总经理张健任新零售部总经理，向王晓雁汇报，汽车销交服部总经理由夏志国担任，同时夏志国继续兼任汽车销交服部销售运营部总经理；任命何俊伶担任甘青宁分公司总经理，向王晓雁汇报。

多位知情人士表示，小米集团原销售运营二部总经理刘耀平，销售运营一部总经理孙昊已从原岗位调任。另有知情人士称，此次的调整跟小米近期中国区业绩“承压”有关，可以理解为王晓雁亲自下场抓业绩。

凤凰网财经《公司研究院》就上述信息向小米求证，截至发稿尚未收到回复。

江苏分公司总经理郭金保此前就曾在运营二部担任副总经理一职，负责过大家电业务的运营。

张健于2024年9月被任命小米汽车部销交服部总经理，距今任职已满一年，今年9月汽车销交服体系就曾有过新任命，原小米人车家与智能产品负责人樊家麟已接任小米汽车销售运营部副总经理一职，直接向夏志国汇报。

某小米头部经销商告诉媒体，受外部环境影响，小米近期开始出现汽车、手机、大家电订单增长放缓的情况，其中不少同行出现空调“压仓”的情况，部分经销商不得不低价向二级市场转卖回收资金，小米面临库存压力。此外，小米也放缓了新零售扩张的节奏，允许经销商对门店进行优化。

值得注意的是，近期小米汽车还因开放“现车选购”，而被外界猜测汽车新增订单已经不复昔日火爆。据官方称，小米汽车现车包含全新车、官方展车、准新车。12月1日12点，已锁单未交付用户可优先改配同车型现车。12月3日10点，现车选购面向全部用户开放。

图片来源：小米汽车

图片来源：小米汽车

上述经销商还表示，小米给了优化汽车门店人员结构的建议，可以从原来的“1+2+11（分别是店长、主管、销售）结构”优化至“1+1+5”结构，结合业务现状提高人效。虽然小米开放了关店通道但实际能关的店并不多，自己只有个位数的门店需要调整优化，不会影响整个公司的运营。

据媒体报道，截至目前各省（直辖市）上报优化门店数量在20～50之间，业内人士预测此次调整门店数量全国大概率将超过1000家。

报道还称，上月，一份王晓雁对经销商群体通知的图片流出。通知指出，基于对当前经营环境的审慎研判，小米之家明确2026年的发展核心将从“规模扩张”转向”质量提升”，小米将启动一项重要的结构性调整:有序关闭部分低效且亏损的门店，以帮助各位伙伴及时止损，将资源聚焦于高潜力门店。

参考报道：

多面体：小米中国区多人员职务调整，涉及手机、汽车、大家电业务"""
    
    # 创建提取器实例
    extractor = NewsEventExtractor()
    
    # 提取事件
    result = extractor.extract_events(news)
    
    # 打印结果
    print("---- Extracted Events ----")
    if "success" in result and not result["success"]:
        print(f"Error: {result['error']}")
        if "raw_output" in result:
            print(f"Raw output: {result['raw_output']}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))