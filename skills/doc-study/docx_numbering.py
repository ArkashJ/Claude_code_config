"""Recover Word AUTO-NUMBERING (the real section numbers) from word/numbering.xml + styles.xml.

INCIDENT 2026-09-29 (Spot BEN-175 golden key): pandoc renders Word auto-numbering as roman-numeral list
items ("i. Purchase Price"), so "Section 2.7" does not exist in `pandoc -t plain` output. 27 of 28 client
agreements were auto-numbered; the real numbers had to be rebuilt from the numbering XML before section_ref
values could be verified at all. Output: one line per non-empty paragraph, "<label> <text>".

usage: docx_numbering.py FILE.docx        (stdlib only; adapted from /tmp/golden/numdump.py)
"""
import sys,re,zipfile
import xml.etree.ElementTree as etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ns={'w':W}
def q(t): return '{%s}%s'%(W,t)
def roman(n):
    r='';
    for v,s in [(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),(50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]:
        while n>=v: r+=s;n-=v
    return r
def fmt(n,f):
    if f=='decimal': return str(n)
    if f=='decimalZero': return '%02d'%n
    if f=='lowerLetter': return chr(96+(n-1)%26+1)*((n-1)//26+1)
    if f=='upperLetter': return chr(64+(n-1)%26+1)*((n-1)//26+1)
    if f=='lowerRoman': return roman(n)
    if f=='upperRoman': return roman(n).upper()
    if f=='none': return ''
    return str(n)
def load(path):
    z=zipfile.ZipFile(path)
    doc=etree.fromstring(z.read('word/document.xml'))
    num=etree.fromstring(z.read('word/numbering.xml')) if 'word/numbering.xml' in z.namelist() else None
    sty=etree.fromstring(z.read('word/styles.xml'))
    return doc,num,sty
def build(num,sty):
    absd={}; nums={}
    if num is None: return absd,nums,{}
    for a in num.findall('w:abstractNum',ns):
        aid=a.get(q('abstractNumId')); lv={}
        for l in a.findall('w:lvl',ns):
            i=int(l.get(q('ilvl')))
            g=lambda t,attr='val':(l.find('w:'+t,ns).get(q(attr)) if l.find('w:'+t,ns) is not None else None)
            lv[i]=dict(fmt=g('numFmt'),text=g('lvlText'),start=int(g('start') or 1),pstyle=g('pStyle'),lgl=l.find('w:isLgl',ns) is not None)
        absd[aid]=lv
    for n in num.findall('w:num',ns):
        nid=n.get(q('numId')); aid=n.find('w:abstractNumId',ns).get(q('val'))
        ov={}
        for o in n.findall('w:lvlOverride',ns):
            s=o.find('w:startOverride',ns)
            if s is not None: ov[int(o.get(q('ilvl')))]=int(s.get(q('val')))
        nums[nid]=(aid,ov)
    # styles -> numPr
    smap={}
    for s in sty.findall('w:style',ns):
        p=s.find('w:pPr/w:numPr',ns)
        ni=il=None
        if p is not None:
            ni=p.find('w:numId',ns); il=p.find('w:ilvl',ns)
        smap[s.get(q('styleId'))]=(ni.get(q('val')) if ni is not None else None, int(il.get(q('val'))) if il is not None else None, (s.find('w:basedOn',ns).get(q('val')) if s.find('w:basedOn',ns) is not None else None))
    return absd,nums,smap
def dump(path):
    doc,num,sty=load(path); absd,nums,smap=build(num,sty)
    counters={}  # aid-> list
    out=[]
    for p in doc.iter(q('p')):
        text=''.join(t.text or '' for t in p.iter(q('t')))
        ppr=p.find('w:pPr',ns); nid=None; il=None
        if ppr is not None:
            np_=ppr.find('w:numPr',ns)
            if np_ is not None:
                ni=np_.find('w:numId',ns); ilv=np_.find('w:ilvl',ns)
                nid=ni.get(q('val')) if ni is not None else None
                il=int(ilv.get(q('val'))) if ilv is not None else None
            ps=ppr.find('w:pStyle',ns)
            if ps is not None:
                sid=ps.get(q('val')); seen=0; sn=None; sl=None
                while sid and seen<12:
                    m=smap.get(sid)
                    if m:
                        if sn is None and m[0] is not None: sn=m[0]
                        if sl is None and m[1] is not None: sl=m[1]
                    sid=m[2] if m else None
                    if m is None:
                        break
                    seen+=1
                if nid is None and sn is not None:
                    nid=sn
                    if il is None:
                        il=sl
                        if il is None:
                            aid0=nums.get(nid,(None,))[0]
                            for k,L in absd.get(aid0,{}).items():
                                if L.get('pstyle')==ps.get(q('val')): il=k
                            if il is None: il=0
                elif nid is not None and il is None:
                    il=sl if sl is not None else 0
        label=''
        if nid and nid!='0' and nid in nums:
            aid,ov=nums[nid]; lv=absd.get(aid,{})
            il=il or 0
            key=aid
            c=counters.setdefault(key,{})
            # reset deeper
            for d in list(c):
                if d>il: del c[d]
            if il in c: c[il]+=1
            else: c[il]=ov.get(il,lv.get(il,{}).get('start',1))
            # ensure parents exist
            for d in range(il):
                if d not in c: c[d]=ov.get(d,lv.get(d,{}).get('start',1))
            L=lv.get(il,{})
            label=L.get('text') or ''
            def rep(m):
                d=int(m.group(1))-1
                return fmt(c.get(d,1),'decimal' if L.get('lgl') else lv.get(d,{}).get('fmt','decimal'))
            label=re.sub(r'%(\d)',rep,label)
        out.append((label,text))
    return out
if __name__=='__main__':
    for lab,t in dump(sys.argv[1]):
        if t.strip(): print((lab+' ' if lab else '')+t)
