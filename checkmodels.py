from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

# 测试模型是否可以正常加载
try:
    model = Wav2Vec2ForCTC.from_pretrained("jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn")
    processor = Wav2Vec2Processor.from_pretrained("jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn")
    print("模型加载成功")
except Exception as e:
    print(f"模型加载失败: {e}")