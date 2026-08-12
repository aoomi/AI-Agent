from __future__ import annotations
import json, unittest
from dataclasses import dataclass
from threading import Event
from ai_agent_llm_gateway import ModelDefinition, OpenAIClientCancelled, OpenAICompatibleClient, OpenAIResponseError, OpenAITransportResponse

@dataclass
class Message: role:str; content:str
class Transport:
    def __init__(self,response):self.response=response;self.request=None
    def post(self,url,headers,body,timeout_seconds,cancellation):self.request=(url,headers,json.loads(body),timeout_seconds);return self.response

class OpenAICompatibleClientTest(unittest.TestCase):
    def setUp(self): self.model=ModelDefinition.create(model_id="gpt-real",provider_id="openai",display_name="Real",capabilities={"chat","structured_output"},context_window=1000)
    def test_structured_completion(self):
        transport=Transport(OpenAITransportResponse(200,json.dumps({"choices":[{"message":{"content":json.dumps({"reply":"ok"})}}]}).encode()))
        client=OpenAICompatibleClient(endpoint="https://api.example.com/v1",api_key="secret",transport=transport)
        result=client.complete(self.model,[Message("user","hello")],{"type":"object","required":["reply"],"properties":{"reply":{"type":"string"}}})
        self.assertEqual(result,{"reply":"ok"});self.assertEqual(transport.request[0],"https://api.example.com/v1/chat/completions");self.assertEqual(transport.request[1]["Authorization"],"Bearer secret")
    def test_invalid_structured_response_is_rejected(self):
        transport=Transport(OpenAITransportResponse(200,b'{"choices":[{"message":{"content":"{}"}}]}'))
        with self.assertRaises(OpenAIResponseError): OpenAICompatibleClient(endpoint="https://api.example.com/v1",api_key="x",transport=transport).complete(self.model,[],{"type":"object","required":["reply"]})
    def test_pre_cancelled_request_never_reaches_transport(self):
        transport=Transport(OpenAITransportResponse(200,b"{}")); cancellation=Event();cancellation.set()
        with self.assertRaises(OpenAIClientCancelled): OpenAICompatibleClient(endpoint="https://api.example.com/v1",api_key="x",transport=transport).complete(self.model,[],{"type":"object"},cancellation=cancellation)
        self.assertIsNone(transport.request)
    def test_insecure_endpoint_and_empty_secret_are_rejected(self):
        with self.assertRaisesRegex(Exception,"HTTPS"):OpenAICompatibleClient(endpoint="http://api.example.com",api_key="x")
        with self.assertRaisesRegex(Exception,"secret"):OpenAICompatibleClient(endpoint="https://api.example.com",api_key="")
    def test_runtime_transport_endpoint_and_request_contracts_are_rejected(self):
        for kwargs in ({"endpoint":"https://user:pass@example.com","api_key":"x"},{"endpoint":"https://example.com","api_key":"x","timeout_seconds":True},{"endpoint":"https://example.com","api_key":"x","transport":object()}):
            with self.subTest(kwargs=kwargs),self.assertRaises(Exception):OpenAICompatibleClient(**kwargs)
        client=OpenAICompatibleClient(endpoint="https://example.com",api_key="x",transport=Transport(OpenAITransportResponse(200,b"{}")))
        for messages,schema in (("message",{}),([],[])):
            with self.subTest(messages=messages,schema=schema),self.assertRaises(Exception):client.complete(self.model,messages,schema)

if __name__=="__main__":unittest.main()
