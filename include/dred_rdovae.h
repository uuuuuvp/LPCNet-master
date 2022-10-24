#include <stdlib.h>

#include "opus_types.h"

typedef struct RDOVAEDecStruct RDOVAEDec;
typedef struct RDOVAEEncStruct RDOVAEEnc;

size_t DRED_rdovae_get_enc_size(void);

size_t DRED_rdovae_get_dec_size(void);

RDOVAEDec * DRED_rdovae_create_decoder(void);

RDOVAEEnc * DRED_rdovae_create_encoder(void);

void DRED_rdovae_init_encoder(RDOVAEEnc *enc_state);

void DRED_rdovae_encode_dframe(RDOVAEEnc *enc_state, float *latents, float *initial_state, const float *input);

void DRED_rdovae_dec_init_states(RDOVAEDec *h, const float * initial_state);

void DRED_rdovae_decode_qframe(RDOVAEDec *h, float *qframe, const float * z);

const opus_int16 * DRED_rdovae_get_p0_pointer(void);
const opus_int16 * DRED_rdovae_get_dead_zone_pointer(void);
const opus_int16 * DRED_rdovae_get_r_pointer(void);
const opus_int16 * DRED_rdovae_get_quant_scales_pointer(void);
