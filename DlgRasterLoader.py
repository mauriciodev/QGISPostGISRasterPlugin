"""
/***************************************************************************
wktRasterDialog
A QGIS plugin
Allows connecting to database and choose wktraster tables.
                             -------------------
begin                : 2010-10-20 
copyright            : (C) 2010 by Mauricio de Paulo
email                : mauricio.dev@gmail.com 
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt4 import QtCore, QtGui 
from ui.DlgRasterLoader import Ui_DlgRasterLoader
from DlgNewConnection import DlgNewConnection
import conn, os, sys
import postgis_utils
from postgis_utils import DbError
import gdal
import re , math

"""sys.path.append("/usr/lib/eclipse/plugins/org.python.pydev.debug_2.2.1.2011071313/pysrc/")
import pydevd
pydevd.settrace()"""

class buffer:
    def __init__(self,connstring):
        parmlist=connstring.split(" ")
        self.db = postgis_utils.GeoDB(host=parmlist[2].split("=")[1],dbname=parmlist[1].split("=")[1],user=parmlist[3].split("=")[1],passwd=parmlist[4].split("=")[1],port=int(parmlist[5].split("=")[1]))
        if self.db==None:
            QtGui.QMessageBox.warning(None,"Error","Connection failed to "+connstring)
            return
        self.cursor = self.db.con.cursor()        
    def write(self,string):
        try:
            self.db._exec_sql(self.cursor, string)
        except DbError, e:
            QtGui.QMessageBox.warning(None,"Error",str(DbError(e)))
            #raise DbError(e)
            
    def commit(self):
        try:
            self.db.con.commit()
        except DbError, e:
            raise DbError(e)
        #del self.db
        


class DlgRasterLoader(QtGui.QDialog,Ui_DlgRasterLoader):
    def __init__(self): 
        QtGui.QDialog.__init__(self) 
        # Set up the user interface from Designer. 
        self.setupUi(self) 
        #connections listing
        self.listDatabases()
        
        self.checkBox.setChecked(False)
        self.widget.setVisible(False)

    def checkPostgisRasterExtension(self,connstring):
        pass
    def getCurrentConnection(self):
        return self.comboBox.currentText()
        
    def browseRaster(self):
        fileName = QtGui.QFileDialog.getOpenFileName(self,"Open Image", os.getcwd(), "GDAL Supported Files (*)");
        if (fileName):
            self.lineEdit.setText(str(fileName))
            self.getMetadata(str(fileName))
        
        
    def loadRaster(self):
        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        
        connstring = str(conn.getConnString(self,self.getCurrentConnection()))
        self.checkPostgisRasterExtension(connstring)
        self.plainTextEdit.appendPlainText("Checking parameters...")
        #running gdal2postgis.py
        fileName=str(self.lineEdit.text())
        tablename=str(self.lineEdit_3.text())#(os.path.split(fileName)[-1])[:-4]
        epsg=str(self.lineEdit_2.text())
        """if (self.checkBox_4.isChecked()):
            blocksizex=str(self.spinBox_2.value())
            blocksizey=str(self.spinBox_3.value())
        else:
            blocksizex=blocksizey=None
        nover=self.spinBox.value()
        isexternal=self.checkBox_2.isChecked()
        isAppend=self.checkBox_3.isChecked()"""
        blocksizex=blocksizey=None
        nover=1
        isexternal=False
        isAppend=False
        import raster2pgsql
        
        cmd=['wktraster','-r',fileName,"-t",tablename,"-s",epsg,"-I","-M"]
        (opts, args)=raster2pgsql.no_command_line(cmd)
        buff=buffer(connstring)
        opts.output=buff
        parmlist=connstring.split(" ")
        buff.write('BEGIN;\n')
        
        if (blocksizex!=None):
            self.cmd+=["-k",blocksizex+"x"+blocksizey]
        if (isexternal): self.cmd.append("-R")
        if (isAppend): self.cmd.append('-a')
        self.connstring=connstring
        self.nover=nover
        #self.sql='python raster2pgsql.py -r '+self.cmd[2]+" -t "+tablename+" -s "+epsg+"-I -M"
        #if( (blocksizex!=None) and (blocksizey!=None)):
        #    self.sql+="-k "+blocksizex+"x"+blocksizey
        raster2pgsql.make_sql_create_table(opts)
        raster2pgsql.wkblify_raster(opts, fileName.replace( '\\', '/') , 0, None)
        buffer.write('END;\n')
        res=buffer.commit()
        if (res!=""): self.plainTextEdit.appendPlainText(str(res)) 
        #self.process=rasterLoaderProcess(connstring, fileName, tablename, epsg, blocksizex, blocksizey, nover, isexternal,isAppend)
        QtCore.QObject.connect(self.process,QtCore.SIGNAL('writeText(PyQt_PyObject)'),self.plainTextEdit.appendPlainText)
        QtCore.QObject.connect(self.process,QtCore.SIGNAL('finished()'),self.finishLoadRaster)
        #self.process.run()
        self.process.start()
        
    
    def finishLoadRaster(self):
        self.plainTextEdit.appendPlainText("Finished.")
        QtGui.QApplication.restoreOverrideCursor()
        
    def getMetadata(self,filename):
        #filename='/home/mauricio/Cartografia_Sistematica/Rio/landsat7_2005/L71217076_07620050617_B10.TIF'
        ds=gdal.Open(filename)
        #pattern that searches for EPSG values
        pattern=re.compile(r'\[?EPSG[^\]]*\]') 
        #captures the every EPSG in the projection description (contains elipsoid, units, etc)
        epsglist=pattern.findall(ds.GetProjection())
        if (len(epsglist)>0):
            epsg=epsglist[-1]
            pattern=re.compile(r'[\'"]\d*[\'"]')
            epsg=pattern.search(epsg)
            if (epsg==None):
                self.lineEdit_2.setText('-1')
            else:
                self.lineEdit_2.setText(epsg.group().strip('\"\'') )
        #computing suggested overview
        nX=math.pow(2,int(math.log(ds.RasterXSize,2))-2)
        nY=math.pow(2,int(math.log(ds.RasterYSize,2))-2)
        self.spinBox_2.setValue(nX)
        self.spinBox_3.setValue(nY)
        #if (ds.RasterXSize>ds.RasterYSize):
        #    min=ds.RasterYSize
        #else:
        #    min=ds.RasterXSize
        #self.spinBox.setValue(int(math.log((min/128),2)))
        self.spinBox.setValue(3)
        
        
        del ds
        
    def listDatabases(self):
        self.comboBox.clear()
        dblist = conn.listDatabases()
        self.comboBox.addItems(dblist.keys())
        
    def newConnection(self):
        self.newConn=DlgNewConnection()
        self.newConn.show()
        self.listDatabases()


if __name__=="__main__":
    app = QtGui.QApplication(sys.argv)
    
    dlg = DlgRasterLoader()
    dlg.show()
    
    retval = app.exec_()
    
    sys.exit(retval)
