#include <cassert>
#include "lunar_calendar.h"
int main(){LunarDate l;
 assert(toLunar(2026,9,29,l)&&l.year==2026&&l.month==8&&l.day==19&&!l.leap);
 assert(toLunar(2026,2,17,l)&&l.month==1&&l.day==1&&!l.leap);
 assert(toLunar(2026,2,16,l)&&l.year==2025&&l.month==12&&l.day==29);
 assert(toLunar(2025,7,25,l)&&l.month==6&&l.day==1&&l.leap);
 assert(!toLunar(1900,1,30,l));assert(!toLunar(2101,1,1,l));
 assert(shichenIndex(23,0)==0&&quarterIndex(23,0)==1);
 assert(shichenIndex(0,0)==0&&quarterIndex(0,0)==5);
 assert(shichenIndex(0,59)==0&&quarterIndex(0,59)==8);
 assert(shichenIndex(1,0)==1&&quarterIndex(1,0)==1);
}
