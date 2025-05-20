#!/usr/bin/python3
import argparse
import yaml


def format_challenge_name(challenge_name):
    return challenge_name.lower().replace('_', '-')


def process_yaml_definition(yaml_path, challenge_name, port, dns_output_path, http_output_path, stream_output_path):
    formatted_challenge = format_challenge_name(challenge_name)
    try:
        with open(yaml_path, 'r') as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
    except Exception as e:
        print(f"Error reading YAML file: {e}")
        return
    
    if 'connection_info' in yaml_content and "docker" not in yaml_content["connection_info"]:
        try:
            with open('./config/dns.tmpl.txt', 'r') as dns_template_file:
                dns_template = dns_template_file.read()
            
            dns_output = dns_template.replace('{{challenge}}', formatted_challenge)
            
            with open(dns_output_path, 'a') as dns_output_file:
                dns_output_file.write(dns_output)
                
            host = f"{formatted_challenge}.ingeneer.ingeniums.club"
            yaml_content["connection_info"] = str(
                yaml_content["connection_info"]
            ).replace("{{host}}", host).replace("{{port}}", str(port))
            print(f"DNS configuration appended for: {challenge_name}")
        except Exception as e:
            print(f"Error processing DNS template: {e}")
    
        if yaml_content.get('protocol') == 'http':
            try:
                with open('./config/http.tmpl.conf', 'r') as http_template_file:
                    http_template = http_template_file.read()
                
                http_output = http_template.replace('{{challenge}}', formatted_challenge).replace('{{port}}', str(port))
                
                url = f"https://{formatted_challenge}.ingeneer.ingeniums.club"
                yaml_content["connection_info"] = str(
                    yaml_content["connection_info"]
                ).replace("{{url}}", url)

                with open(http_output_path, 'a') as http_output_file:
                    http_output_file.write(http_output)
                    
                print(f"HTTP configuration appended for {challenge_name}")
            except Exception as e:
                print(f"Error processing Nginx template: {e}")
        else:
            try:
                with open('./config/stream.tmpl.conf', 'r') as stream_template_file:
                    stream_template = stream_template_file.read()
                
                http_output = stream_template.replace('{{challenge}}', formatted_challenge).replace('{{port}}', str(port))
                
                url = f"https://{formatted_challenge}.ingeneer.ingeniums.club"
                yaml_content["connection_info"] = str(
                    yaml_content["connection_info"]
                ).replace("{{url}}", url)

                with open(stream_output_path, 'a') as stream_output_file:
                    stream_output_file.write(http_output)
                    
                print(f"Stream configuration appended for {challenge_name}")
            except Exception as e:
                print(f"Error processing Nginx template: {e}")

    with open(yaml_path, "w") as yaml_file:
        yaml_file.write(yaml.dump(yaml_content))


def main():
    parser = argparse.ArgumentParser(description='Process YAML definition and generate configuration files.')
    parser.add_argument('yaml_path', help='Path to the YAML definition file')
    parser.add_argument('challenge_name', help='Name of the challenge')
    parser.add_argument('port', type=int, help='Port number')
    # parser.add_argument('dns_output_path', help='Path to the DNS output file')
    # parser.add_argument('nginx_output_path', help='Path to the Nginx configuration output file')
    
    args = parser.parse_args()
    
    process_yaml_definition(
        args.yaml_path,
        args.challenge_name,
        args.port,
        "./config/dns.txt",
        "./config/http.conf",
        "./config/stream.conf"
    )


if __name__ == "__main__":
    main()
