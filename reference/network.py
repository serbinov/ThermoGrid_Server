# file: network.py
import socketserver
import socket
import json
from PySide6.QtCore import QObject, Signal, Slot

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def setup(self):
        super().setup()
        self.worker = self.server.worker
        try:
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
            
    def handle(self):
        self.request.settimeout(20.0)
        client_address = self.client_address[0]
        self.worker.log_message.emit(f"Новое подключение от {client_address}")
        full_data_bytes = bytearray()
        
        while True:
            try:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                full_data_bytes.extend(chunk)
            except socket.timeout:
                self.worker.log_message.emit(f"Таймаут ожидания данных от {client_address}.")
                break
            except Exception as e:
                self.worker.log_message.emit(f"Ошибка чтения сокета от {client_address}: {e}")
                return

        if not full_data_bytes:
            self.worker.log_message.emit(f"Клиент {client_address} отключился, не отправив данных.")
            return
            
        try:
            full_data_str = full_data_bytes.decode('utf-8', errors='ignore')
            separator = "\r\n\r\n"
            json_body = full_data_str.partition(separator)[2] if separator in full_data_str else full_data_str
            json_body = json_body.strip()
            
            if not json_body:
                self.worker.log_message.emit(f"Принят пакет от {client_address}, но тело JSON пустое.")
                return
                
            self.worker.log_message.emit(f"Принят полный пакет от {client_address}: {json_body[:300]}...")
            data_dict = json.loads(json_body)
            self.worker.data_received.emit(data_dict)
            
        except json.JSONDecodeError as e:
            self.worker.log_message.emit(f"Ошибка декодирования JSON от {client_address}: {e}. Полное тело: '{full_data_str}'")
        except Exception as e:
            self.worker.log_message.emit(f"Критическая ошибка при обработке данных от {client_address}: {e}, {type(e)}")

class CustomTCPServer(socketserver.ThreadingTCPServer):
    def __init__(self, server_address, RequestHandlerClass, worker):
        super().__init__(server_address, RequestHandlerClass)
        self.worker = worker
        self.allow_reuse_address = True

class ServerWorker(QObject):
    data_received = Signal(dict)
    log_message = Signal(str)

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None

    @Slot()
    def run(self):
        try:
            self.log_message.emit(f"Попытка запуска сервера на {self.host}:{self.port}")
            self.server = CustomTCPServer((self.host, self.port), ThreadedTCPRequestHandler, worker=self)
            self.log_message.emit(f"Сервер успешно запущен на {self.host}:{self.port}")
            self.server.serve_forever()
        except OSError as e:
            self.log_message.emit(f"ОШИБКА запуска сервера на порту {self.port}: {e}")
        except Exception as e:
            self.log_message.emit(f"Критическая ошибка в потоке сервера: {e}")

    def shutdown(self):
        if self.server:
            self.log_message.emit("Остановка сервера...")
            self.server.shutdown()
            self.server.server_close()
            self.log_message.emit("Сервер остановлен.")