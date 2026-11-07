#include "core.h"
#include <math.h>
#include <string.h>
void pid_reset(Pid *p) { memset(p,0,sizeof(*p)); }
static float clamp(float x,float lo,float hi) { return fminf(hi,fmaxf(lo,x)); }
float pid_step(Pid *p,float sp,float pv,float dt,float kp,float ki,float kd,float tau,float max) {
    if(!isfinite(sp)||!isfinite(pv)||!isfinite(dt)||dt<=0||!isfinite(max)||max<0) {
        pid_reset(p); return 0;
    }
    float error=sp-pv, derivative=0;
    if(p->initialized) derivative=-(pv-p->last_pv)/dt;
    p->derivative+=dt/(tau+dt)*(derivative-p->derivative);
    p->last_pv=pv; p->initialized=true;
    float proportional=kp*error, d=kd*p->derivative;
    float candidate=p->integral+ki*error*dt;
    float sum=proportional+candidate+d;
    /* Conditional integration, including recovery while saturated. */
    if((sum>=0 && sum<=max)||(sum>max && error<0)||(sum<0 && error>0))
        p->integral=clamp(candidate,-max,max);
    return clamp(proportional+p->integral+d,0,max);
}
