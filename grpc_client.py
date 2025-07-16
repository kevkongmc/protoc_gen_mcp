import grpc
from helloworld import hello_service_pb2
from helloworld import hello_service_pb2_grpc

def run():
    # Connect to the server on localhost:50051
    with grpc.insecure_channel('localhost:50051') as channel:
        # Create a stub (client)
        stub = hello_service_pb2_grpc.GreeterStub(channel)
        
        # Call the SayHello RPC
        name = input("Enter your name: ")
        response = stub.SayHello(hello_service_pb2.HelloRequest(name=name))
        print("Server response:", response.message)

if __name__ == '__main__':
    run()
