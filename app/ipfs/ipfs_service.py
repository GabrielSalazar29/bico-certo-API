import ipfshttpclient
from typing import Dict, Any, Optional, Tuple
from ..config.settings import settings


class IPFSService:
    """Serviço para interação com IPFS local"""

    def __init__(self, api_url: str = None):
        """
        Inicializa conexão com IPFS
        Default: /ip4/127.0.0.1/tcp/5001 (IPFS local)
        """
        self.api_url = api_url or settings.IPFS_API_URL or '/ip4/127.0.0.1/tcp/5001'

        try:
            self.client = ipfshttpclient.connect(self.api_url)

            # Verificar se IPFS está rodando
            node_info = self.client.id()
            print(f"[IPFS] Node ID: {node_info['ID']}")

        except Exception as e:
            raise Exception(f"IPFS não está disponível: {e}")

   
   
    def add_bytes_to_ipfs(self, data_bytes: bytes) -> Tuple[bool, str, Optional[str]]:
        """
        Adiciona bytes puros (como um arquivo de imagem) ao IPFS.
        Retorna: (sucesso, mensagem, cid)
        """
        try:
            # 💡 Adiciona os bytes diretamente ao IPFS
            result = self.client.add_bytes(data_bytes) 
            print(f" Resultado do Resul {result},  >>>> Type: {type(result)}")
            # Caso o resul retorne apenas uma string hash do CID
            if isinstance(result, str):
                cid = result    
            
            #Caso o result seja um dicionario contendo o hash do CID
            elif isinstance(result, dict) and 'Hash' in result:
            # CASO 2: A biblioteca retornou o dicionário padrão (JSON).
                cid = result['Hash']
            
            else:
            # Resposta inválida (não é string nem dict com 'Hash')
                print(f"\nResposta do IPFS inválida: {result}\n")
                return False, f"Resposta do IPFS inválida: {result}", None

            # Verifica se o CID foi encontrado
            if not cid:
                print("O CID não foi encontrado na resposta do IPFS.")
                return False, "O CID não foi encontrado na resposta do IPFS.", None
                          
            self.client.pin.add(cid)
            
            print(f"Enviado para o IPFS!:{cid}")
            return True, "Bytes adicionados ao IPFS com sucesso", cid

        except Exception as e:
            print(f"Erro ao adicionar bytes ao IPFS: {str(e)}")
            return False, f"Erro ao adicionar bytes ao IPFS: {str(e)}", None
        

    def add_data_to_ipfs(self, data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Adiciona dados do job ao IPFS
        Retorna: (sucesso, mensagem, cid)
        """
        try:
            # Adicionar timestamp e versão
            ipfs_data = {
                "data": data
            }

            # Adicionar ao IPFS
            result = self.client.add_json(ipfs_data)
            cid = result

            self.client.pin.add(cid)

            print(f"Salvo os dados do openjob: cid: {cid}")
            return True, "Dados adicionados ao IPFS com sucesso", cid

        except Exception as e:
            return False, f"Erro ao adicionar ao IPFS: {str(e)}", None

    def get_job_data(self, cid: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Recupera dados do job do IPFS usando o CID
        Retorna: (sucesso, mensagem, dados)
        """
        try:
            data = self.client.get_json(cid)

            return True, "Dados recuperados do IPFS", data

        except Exception as e:
            return False, f"Erro ao recuperar do IPFS: {str(e)}", None

    def unpin_cid(self, cid: str) -> bool:
        """
        Remove fixação de um CID
        """
        try:
            self.client.pin.rm(cid)
            return True
        except Exception as e:
            return False