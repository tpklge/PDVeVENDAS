// Actual vendor TLS client: application bytes only after certificate verification.
#include "mbedtls/net_sockets.h"
#include "mbedtls/ssl.h"
#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/x509_crt.h"
#include <cstring>
int main(int argc,char** argv){
    if(argc!=5)return 2;
    mbedtls_net_context net;mbedtls_net_init(&net);
    mbedtls_ssl_context ssl;mbedtls_ssl_init(&ssl);
    mbedtls_ssl_config config;mbedtls_ssl_config_init(&config);
    mbedtls_entropy_context entropy;mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_context random;mbedtls_ctr_drbg_init(&random);
    mbedtls_x509_crt ca;mbedtls_x509_crt_init(&ca);
    int rc=mbedtls_ctr_drbg_seed(&random,mbedtls_entropy_func,&entropy,nullptr,0);
    if(rc==0)rc=mbedtls_x509_crt_parse_file(&ca,argv[2]);
    if(rc==0)rc=mbedtls_ssl_config_defaults(&config,MBEDTLS_SSL_IS_CLIENT,MBEDTLS_SSL_TRANSPORT_STREAM,MBEDTLS_SSL_PRESET_DEFAULT);
    mbedtls_ssl_conf_authmode(&config,MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_min_tls_version(&config,MBEDTLS_SSL_VERSION_TLS1_2);
    mbedtls_ssl_conf_max_tls_version(&config,MBEDTLS_SSL_VERSION_TLS1_2);
    mbedtls_ssl_conf_ca_chain(&config,&ca,nullptr);
    mbedtls_ssl_conf_rng(&config,mbedtls_ctr_drbg_random,&random);
    if(rc==0)rc=mbedtls_ssl_setup(&ssl,&config);
    if(rc==0)rc=mbedtls_ssl_set_hostname(&ssl,argv[3]);
    if(rc==0)rc=mbedtls_net_connect(&net,"127.0.0.1",argv[1],MBEDTLS_NET_PROTO_TCP);
    mbedtls_ssl_set_bio(&ssl,&net,mbedtls_net_send,mbedtls_net_recv,nullptr);
    if(rc==0){do{rc=mbedtls_ssl_handshake(&ssl);}while(rc==MBEDTLS_ERR_SSL_WANT_READ||rc==MBEDTLS_ERR_SSL_WANT_WRITE);}
    bool valid=rc==0&&mbedtls_ssl_get_verify_result(&ssl)==0;
    bool sent=false;
    if(valid){const unsigned char message[]="verified";sent=mbedtls_ssl_write(&ssl,message,sizeof(message)-1)==static_cast<int>(sizeof(message)-1);}
    mbedtls_net_free(&net);mbedtls_ssl_free(&ssl);mbedtls_ssl_config_free(&config);
    mbedtls_x509_crt_free(&ca);mbedtls_ctr_drbg_free(&random);mbedtls_entropy_free(&entropy);
    return (strcmp(argv[4],"valid")==0?valid&&sent:!valid&&!sent)?0:1;
}
