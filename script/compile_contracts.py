import solcx
import os
import json


def compile_contracts():
    """
    Compila todos os contratos Solidity do projeto usando a versão especificada do solc.
    """
    # Define o diretório raiz do projeto (um nível acima da pasta script)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Define os caminhos relativos ao diretório raiz
    contracts_dir = os.path.join(project_root, 'contracts')
    build_dir = os.path.join(project_root, 'build')
    
    # Define a versão do solc a ser utilizada, compatível com as declarações de pragma
    solc_version = '0.8.20'
    
    # Instala e configura a versão do solc
    print(f"Instalando e configurando a versão do solc para {solc_version}...")
    solcx.install_solc(solc_version)
    solcx.set_solc_version(solc_version)

    contracts_to_compile = [
        "BicoCertoAdmin.sol",
        "BicoCertoDisputeResolver.sol",
        "BicoCertoJobManager.sol",
        "BicoCertoPaymentGateway.sol",
        "BicoCertoRegistry.sol",
        "BicoCertoReputation.sol",
        "BicoCerto.sol"
    ]

    # Cria o diretório de build se não existir
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
        print(f"Diretório 'build' criado em: {build_dir}")

    # Compila cada contrato
    for contract_file in contracts_to_compile:
        contract_file_path = os.path.join(contracts_dir, contract_file)
        
        if not os.path.exists(contract_file_path):
            print(f"Aviso: {contract_file} não encontrado em {contracts_dir}. Pulando.")
            continue
            
        print(f"Compilando {contract_file}...")
        try:
            # Muda o diretório de trabalho temporariamente para o diretório raiz
            # Isso ajuda com as importações relativas nos contratos Solidity
            original_cwd = os.getcwd()
            os.chdir(project_root)
            
            compiled_sol = solcx.compile_files(
                [contract_file_path],
                output_values=["abi", "bin"],
                solc_version=solc_version,
                base_path=project_root,  # Define o caminho base para resolução de imports
                allow_paths=[contracts_dir],  # Permite importações da pasta contracts
                optimize=True,  # ≤- Parâmetro correto para ativar o otimizador
                optimize_runs=200,  
                via_ir=True
            )
            
            # Volta ao diretório original
            os.chdir(original_cwd)
            
            # Salva os arquivos ABI e BIN
            for contract_name_long, contract_data in compiled_sol.items():
                contract_name = contract_name_long.split(':')[-1]
                
                # Escreve o ABI
                abi_path = os.path.join(build_dir, f'{contract_name}_sol_{contract_name}.abi')
                with open(abi_path, 'w') as f:
                    json.dump(contract_data['abi'], f, indent=4)
                
                # Escreve o BIN
                bin_path = os.path.join(build_dir, f'{contract_name}_sol_{contract_name}.bin')
                with open(bin_path, 'w') as f:
                    f.write(contract_data['bin'])

        except Exception as e:
            print(f"Erro ao compilar {contract_file}: {e}")
            # Garante que voltamos ao diretório original mesmo em caso de erro
            if 'original_cwd' in locals():
                os.chdir(original_cwd)

    print("\nCompilação concluída com sucesso!")
    print(f"Arquivos compilados salvos em: {build_dir}")


if __name__ == "__main__":
    compile_contracts()
