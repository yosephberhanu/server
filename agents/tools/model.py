import json
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey, or_
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Declare base for SQLAlchemy ORM
Base = declarative_base()

# ========================
# UML Class Representation
# ========================
class UMLClass(Base):
    __tablename__ = 'uml_class'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    package_name = Column(String)
    is_abstract = Column(Boolean)
    is_interface = Column(Boolean)
    annotations = Column(Text)
    files = Column(Text)
    dom_id = Column(Text)
    display_name = Column(Text)
    summary = Column(Text)
    comments = Column(Text)

    # One class has many properties and methods
    properties = relationship("UMLProperty", back_populates="uml_class")
    methods = relationship("UMLMethod", back_populates="uml_class")

# ========================
# UML Property (Field)
# ========================
class UMLProperty(Base):
    __tablename__ = 'uml_property'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('uml_class.id'))
    name = Column(String)
    data_type = Column(String)
    visibility = Column(String)
    is_static = Column(Boolean)
    is_final = Column(Boolean)
    source_line = Column(Integer)
    dom_id = Column(Text)
    annotations = Column(Text)
    comments = Column(Text)
    summary = Column(Text)

    uml_class = relationship("UMLClass", back_populates="properties")

# ========================
# UML Method
# ========================
class UMLMethod(Base):
    __tablename__ = 'uml_method'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('uml_class.id'))
    name = Column(String)
    dom_id = Column(Text)
    return_type = Column(String)
    visibility = Column(String)
    is_static = Column(Boolean)
    is_abstract = Column(Boolean)
    starting_line = Column(Integer)
    ending_line = Column(Integer)
    source = Column(Text)
    annotations = Column(Text)
    display_name = Column(Text)
    comments = Column(Text)
    summary = Column(Text)

    uml_class = relationship("UMLClass", back_populates="methods")
    parameters = relationship("UMLParameter", back_populates="method")

# ========================
# UML Method Parameters
# ========================
class UMLParameter(Base):
    __tablename__ = 'uml_parameter'
    id = Column(Integer, primary_key=True)
    method_id = Column(Integer, ForeignKey('uml_method.id'))
    name = Column(String)
    dom_id = Column(Text)
    data_type = Column(String)
    display_name = Column(Text)
    annotations = Column(Text)
    comments = Column(Text)
    summary = Column(Text)

    method = relationship("UMLMethod", back_populates="parameters")

# ========================
# Class-level or Package-level Relationships
# ========================
class UMLRelationship(Base):
    __tablename__ = "uml_relationship"
    id = Column(Integer, primary_key=True)
    source = Column(String)  # fully-qualified class name or package
    target = Column(String)
    name = Column(String)    # e.g., "uses", "calls", "depends"
    type = Column(String)    # e.g., "composition", "association"

# ========================
# UML Package (Nested)
# ========================
class UMLPackage(Base):
    __tablename__ = "uml_package"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    parent = Column(String)  # e.g., 'org.example' is parent of 'org.example.module'


# ========================
# Main Tool Class for LangGraph
# ========================
class SourceTools:
    def __init__(self, data='sqlite:///uml-data.db'):
        self.engine = create_engine(data)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_source(self, file_name: str):
        """
        Return source code snippets from methods belonging to the given file name.

        Parameters:
            file_name (str): The name (or partial path) of the file

        Returns:
            dict: Source code grouped by class name
        """
        try:
            # Step 1: Find all classes that contain this file
            classes = self.session.query(UMLClass).filter( UMLClass.files.like(f"%{file_name}%") ).all()

            if not classes:
                return {"error": f"No classes found for file: {file_name}"}

            result = {}
            for cls in classes:
                fqcn = f"{cls.package_name}.{cls.name}" if cls.package_name else cls.name
                result[fqcn] = []

                # Step 2: Get method sources from this class
                for method in cls.methods:
                    result[fqcn].append({
                        "method": method.name,
                        "source": method.source
                    })

            return result

        except Exception as e:
            return {"error": str(e)}

    # Tool: Get all classes in a package
    def get_classes(self, package_name: str):
        result = {
            "type": "class",
            "classes": [],
            "relationships": []
        }

        if not package_name:
            classes = self.session.query(UMLClass).all()
            relationships = self.session.query(UMLRelationship).all()
        else:
            classes = self.session.query(UMLClass).filter(UMLClass.package_name == package_name).all()
            class_names = [f"{cls.package_name}.{cls.name}" for cls in classes]
            relationships = self.session.query(UMLRelationship).filter(
                or_(
                    UMLRelationship.source.in_(class_names),
                    UMLRelationship.target.in_(class_names)
                )
            ).all()

        for cls in classes:
            class_dict = {
                "type": "class",
                "annotations": "",
                "id": f"{cls.package_name}.{cls.name}",
                "domId": cls.dom_id or "",
                "name": cls.name,
                "package": cls.package_name,
                "style": "",
                "generatedContent": "",
                "files": json.loads(cls.files) if cls.files else [],
                "isAbstract": bool(cls.is_abstract),
                "isInterface": bool(cls.is_interface),
                "properties": [],
                "methods": []
            }

            for prop in cls.properties:
                class_dict["properties"].append({
                    "name": prop.name,
                    "dataType": prop.data_type,
                    "annotations": "",
                    "visibility": prop.visibility,
                    "isStatic": bool(prop.is_static),
                    "isFinal": bool(prop.is_final)
                })

            for method in cls.methods:
                method_dict = {
                    "name": method.name,
                    "returnType": method.return_type,
                    "annotations": "",
                    "visibility": method.visibility,
                    "isStatic": bool(method.is_static),
                    "isAbstract": bool(method.is_abstract),
                    "parameters": []
                }

                for param in method.parameters:
                    method_dict["parameters"].append({
                        "name": param.name,
                        "dataType": param.data_type,
                        "annotations": json.loads(param.annotations) if param.annotations else []
                    })

                class_dict["methods"].append(method_dict)

            result["classes"].append(class_dict)

        for rls in relationships:
            rls_dict = {
                "id": str(rls.id),
                "name": rls.name,
                "source": rls.source,
                "target": rls.target,
                "type": rls.type
            }
            result["relationships"].append(rls_dict)

        return result

    # Tool: Get a package and its immediate children (classes + subpackages)
    def get_packages(self, package_name: str):
        result = {
            "type": "package",
            "id": package_name or "",
            "name": package_name.split(".")[-1] if package_name else "",
            "packages": [],
            "classes": [],
            "relationships": []
        }

        # Step 1: Get classes and direct subpackages in this package
        if not package_name:
            classes = self.session.query(UMLClass).filter(UMLClass.package_name.is_(None)).all()
            subpackages = self.session.query(UMLPackage).filter(UMLPackage.parent.is_(None)).all()
        else:
            classes = self.session.query(UMLClass).filter(UMLClass.package_name == package_name).all()
            subpackages = self.session.query(UMLPackage).filter(UMLPackage.parent == package_name).all()

        # Step 2: Build mapping of class names to package
        package_scope_class_map = {}
        all_package_names = set()

        for cls in classes:
            fqcn = f"{cls.package_name}.{cls.name}" if cls.package_name else cls.name
            package_scope_class_map[fqcn] = cls.package_name or ""
            all_package_names.add(cls.package_name or "")

        for subpkg in subpackages:
            full_pkg = f"{subpkg.parent}.{subpkg.name}" if subpkg.parent else subpkg.name
            has_children = self.session.query(UMLPackage).filter(UMLPackage.parent == full_pkg).first() is not None
            all_package_names.add(full_pkg)

            # Build subpackage node
            subpkg_dict = {
                "type": "package",
                "annotation": "",
                "id": full_pkg,
                "name": subpkg.name,
                "package": subpkg.parent or "",
                "on_click": f"/data/packages?{full_pkg}" if has_children else f"/data/classes?{full_pkg}",
                "subpackages": [],
                "classes": []
            }
            result["packages"].append(subpkg_dict)

            subpkg_classes = self.session.query(UMLClass).filter(UMLClass.package_name == full_pkg).all()
            for cls in subpkg_classes:
                fqcn = f"{cls.package_name}.{cls.name}"
                package_scope_class_map[fqcn] = cls.package_name

        # Step 3: Add classes directly under this package
        for cls in classes:
            result["classes"].append({
                "type": "class",
                "annotation": "",
                "id": f"{cls.package_name}.{cls.name}" if cls.package_name else cls.name,
                "name": cls.name,
                "package": cls.package_name or ""
            })

        # Step 4: Aggregate class-level relationships into package-level edges
        all_relationships = self.session.query(UMLRelationship).all()
        seen_package_pairs = set()

        for r in all_relationships:
            src_pkg = package_scope_class_map.get(r.source)
            tgt_pkg = package_scope_class_map.get(r.target)

            if src_pkg and tgt_pkg and src_pkg != tgt_pkg:
                key = (src_pkg, tgt_pkg)
                if key not in seen_package_pairs:
                    seen_package_pairs.add(key)
                    result["relationships"].append({
                        "id": f"{src_pkg}->{tgt_pkg}",
                        "label": r.name or "",
                        "source": src_pkg,
                        "target": tgt_pkg,
                        "type": r.type
                    })

        return result

    def __del__(self):
        self.session.close()


# ========================
# LangGraph Tool Definitions
# ========================

if __name__ == "__main__":
    st = SourceTools()
    output = json.dumps(st.get_packages("org.keycloak.themeverifier"), indent=2)
    print(output)