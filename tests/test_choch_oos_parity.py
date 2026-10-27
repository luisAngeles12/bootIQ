"""Paridad OOS CHOCH: narrativa vieja vs corregida; ejecución sin bróker."""
import json
import subprocess
import sys
import unittest

WORKER = r'''
import ast, contextlib, csv, io, json, pathlib, sys, tempfile, types
fake=types.ModuleType("credenciales_local")
fake.EMAIL=fake.PASSWORD=""
sys.modules["credenciales_local"]=fake
import config
import backtest_bot_real as bt
import estrategia
assert config.MODO_CUENTA=="PRACTICE"
assert bt.MODO_EXPERIMENTO=="OUT_OF_SAMPLE"
assert bt.MODO_BACKTEST=="FILTRADO"
assert not bt.ACTUALIZAR_APRENDIZAJE
assert not bt.ACTUALIZAR_APRENDIZAJE_PROTOCOLO
assert len(bt.cargar_datasets())==17

if sys.argv[1]=="anterior":
    import motor_estrategias
    fuente=pathlib.Path(motor_estrategias.__file__).read_text(encoding="utf-8")
    arbol=ast.parse(fuente)
    class RestaurarNarrativa(ast.NodeTransformer):
        def visit_IfExp(self,node):
            node=self.generic_visit(node)
            if isinstance(node.body,ast.Constant) and isinstance(node.orelse,ast.Constant):
                if (node.body.value,node.orelse.value)==("EMA favorece compra","EMA no favorece compra"):
                    return ast.copy_location(ast.Constant("EMA favorece compra"),node)
                if (node.body.value,node.orelse.value)==("EMA favorece venta","EMA no favorece venta"):
                    return ast.copy_location(ast.Constant("EMA favorece venta"),node)
            return node
        def visit_Constant(self,node):
            if node.value=="CHOCH detectado; contexto pendiente de validación":
                return ast.copy_location(ast.Constant("CHOCH con contexto confirmado"),node)
            return node
    arbol=ast.fix_missing_locations(RestaurarNarrativa().visit(arbol))
    namespace=dict(vars(motor_estrategias))
    exec(compile(arbol,"<choch_anterior>","exec"),namespace)
    estrategia.motor_estrategias_profesional=namespace["motor_estrategias_profesional"]

campos=("fecha_senal","activo","patron","direccion","puntaje","score_final",
        "estado_operacion","cerebro_unico_decision","origen_autoridad",
        "core4_rescate","core4_reglas","resultado_hipotetico")
with tempfile.TemporaryDirectory(prefix="choch_oos_") as temp:
    bt.SALIDA=str(pathlib.Path(temp)/"replay.csv")
    with contextlib.redirect_stdout(io.StringIO()):
        bt.main()
    with open(bt.SALIDA,encoding="utf-8-sig",newline="") as entrada:
        filas=[{k:f.get(k,"") for k in campos} for f in csv.DictReader(entrada)]
assert len(filas)==39,len(filas)
print(json.dumps(filas,ensure_ascii=False))
'''


class ChochOosParity(unittest.TestCase):
    def test_oos_39_senales_conservan_decisiones(self):
        resultados=[]
        for modo in ("anterior","corregida"):
            run=subprocess.run([sys.executable,"-c",WORKER,modo],
                               capture_output=True,text=True,timeout=240)
            self.assertEqual(run.returncode,0,run.stderr[-4000:])
            resultados.append(json.loads(run.stdout))
        self.assertEqual(resultados[0],resultados[1])


if __name__=="__main__":
    unittest.main()
